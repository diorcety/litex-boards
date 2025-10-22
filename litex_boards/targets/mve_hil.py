#!/usr/bin/env python3
#
# This file is part of LiteX-Boards.
#
# Copyright (c) 2021 Antmicro <www.antmicro.com>
# Copyright (c) 2022 IBM Corp.
# SPDX-License-Identifier: BSD-2-Clause


from collections import defaultdict
import json
import logging
import math

from migen import *
from migen.util.misc import xdir

from litex.gen import *

from litex_boards.platforms import mve_hil

from litex.build.generic_platform import IOStandard, Pins, Subsignal

from litex.soc.cores.can.ctu_can_fd import CTUCANFD
from litex.soc.cores.gpio import GPIOIn, GPIOOut
from litex.soc.integration.soc import SoCRegion
from litex.soc.interconnect.csr import CSRConstant

from litex.soc.cores.clock import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.cores.led import LedChaser
from litex.soc.cores.i2c import I2CMaster

from litedram.modules import NT5CC128M16
from litedram.phy import s7ddrphy

from liteeth.phy import LiteEthS7PHYRGMII

# GPIOInOut ----------------------------------------------------------------------------------------

class GPIOInOut(LiteXModule):
    def __init__(self, in_pads, out_pads, with_irq=False):
        self.gpio_in  = GPIOIn(in_pads, with_irq) if in_pads is not None else None
        self.gpio_out = GPIOOut(out_pads) if out_pads is not None else None
        if self.gpio_in and with_irq:
            self.ev = self.gpio_in.ev
        self.in_ngpio  = CSRConstant(len(in_pads) if in_pads is not None else 0)
        self.out_ngpio  = CSRConstant(len(out_pads) if out_pads is not None else 0)

    def get_csrs(self):
        csrs = []
        if self.gpio_in:
            csrs += self.gpio_in.get_csrs()
        if self.gpio_out:
            csrs += self.gpio_out.get_csrs()
        return csrs
    
    def dts(self, name, d):
        if name not in d["csr_bases"]:
            return 0, ""
        dts = """
&soc {{
    #address-cells = <1>;
    #size-cells    = <1>;
    interrupt-parent = <&intc0>;
    {name}_in: gpio@{csr_base_in:x} {{
            compatible = "litex,gpio";
            reg = <0x{csr_base_in:x} 0x4>;
            interrupts = <{interrupts}>;
            #address-cells = <0>;
            gpio-controller;
            #gpio-cells = <2>;
            interrupt-controller;
            #interrupt-cells = <2>;
            litex,ngpio = <{ngpio_in}>;
            litex,direction = "in";
            status = "okay";
    }};

    {name}_out: gpio@{csr_base_out:x} {{
            compatible = "litex,gpio";
            reg = <0x{csr_base_out:x} 0x4>;
            gpio-controller;
            #gpio-cells = <2>;
            litex,ngpio = <{ngpio_out}>;
            litex,direction = "out";
            status = "okay";
    }};
}};
""".format(
            name=name, 
            csr_base_in=d["csr_bases"][name],
            interrupts=d["constants"][f"{name}_interrupt"],
            ngpio_in=d["constants"][f"{name}_in_ngpio"],
            csr_base_out=d["csr_bases"][name] + 4,
            ngpio_out=d["constants"][f"{name}_out_ngpio"])
        return 0, dts

# KTS1622 ------------------------------------------------------------------------------------------

class KTS1622(LiteXModule):
    def __init__(self, i2c_name, interrupt=None, reset=None):
        self._i2c_name = i2c_name
        self._interrupt = interrupt
        self._reset = reset

    def dts(self, name, d):
        
        dts = """
&{i2c_name} {{
    #address-cells = <1>;
    #size-cells = <0>;
    status = "okay";
    {i2c_name}@20 {{
        compatible = "nxp,pca6416";
        reg = <0x20>;
        gpio-controller;""".format(i2c_csr_base=d["csr_bases"][self._i2c_name], i2c_name=self._i2c_name, name=name)
        if self._reset != None:
            dts += """
        reset-gpios = <&{gpio_name} {gpio_number} 1>;""".format(gpio_name = self._reset[0], gpio_number = self._reset[1])
        if self._interrupt != None:
            dts += """
        interrupt-parent = <&{gpio_name}>;
        interrupts = <{gpio_number} 2>;""".format(gpio_name = self._interrupt[0], gpio_number = self._interrupt[1])
        dts += """
    };
};
"""
        return 10, dts

# CRG ----------------------------------------------------------------------------------------------

class _CRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq, with_dram):
        self.rst       = Signal()
        self.cd_sys    = ClockDomain()
        if with_dram:
            self.cd_sys4x     = ClockDomain()
            self.cd_sys4x_dqs = ClockDomain()
            self.cd_idelay    = ClockDomain()
                
        # Clk
        clk200 = platform.request("clk200")

        # PLL.
        self.pll = pll = S7PLL(speedgrade=-2)
        self.comb += pll.reset.eq(self.rst)
        pll.register_clkin(clk200, 200e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)
        pll.reset.attr.add("keep")
        platform.add_platform_command("set_false_path -through [get_nets {reset}]", reset=pll.reset)
        if with_dram:
            pll.create_clkout(self.cd_sys4x,     4*sys_clk_freq)
            pll.create_clkout(self.cd_sys4x_dqs, 4*sys_clk_freq, phase=90)
            pll.create_clkout(self.cd_idelay,    200e6)
        
        # IdelayCtrl.
        if with_dram:
            self.idelayctrl = S7IDELAYCTRL(self.cd_idelay)

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    def add_extension(self, platform, name, index, *args):
        extension = [tuple([name, index] + list(args))]
        platform.add_extension(extension)
        return platform.request(name, index)

    def _add_can(self, platform, port, tx, rx, suffix=""):
        pads = self.add_extension(
            platform, "can", port, 
            Subsignal("tx", Pins(f"con{port}:{tx}")),
            Subsignal("rx", Pins(f"con{port}:{rx}")),
            IOStandard("LVCMOS33")
        )

        can_name = f"can{port}{suffix}"
        can = CTUCANFD(platform, pads, txt_buffer_count=4, rx_buffer_size=128, test_registers=False)
        self.add_module(name=can_name, module=can)
        region = SoCRegion(origin = self.mem_map.get(can_name, None),
            size   = 0x10000,
            mode   = "rw",
            cached = False,
        )
        self.bus.add_slave(can_name, can.bus, region)
        self.irq.add(can_name)

    def add_con_can2(self, platform, port):
        self.logger.info(f"Port {port}: CAN2")
        self._add_can(platform, port, 2, 3, suffix="_0")
        self._add_can(platform, port, 0, 1, suffix="_1")

    def add_con_rs(self, platform, port):
        self.logger.info(f"Port {port}: RS")

        pads = self.add_extension(
            platform, "uart", port,
            Subsignal("tx", Pins(f"con{port}:3")),
            Subsignal("rx", Pins(f"con{port}:2")),
            Subsignal("rts", Pins(f"con{port}:1")),
            Subsignal("cts", Pins(f"con{port}:0")),
            IOStandard("LVCMOS33")
        )
    
        ## Create module
        serial_name = f"uart{port}"
        from litex.soc.cores.uart import UARTPHY, UART
        uart_kwargs    = {
            "tx_fifo_depth": 16,
            "rx_fifo_depth": 16,
        }
        uart_phy  = UARTPHY(pads, clk_freq=self.sys_clk_freq, baudrate=115200, with_dynamic_baudrate=True)
        uart      = UART(uart_phy, **uart_kwargs)
        self.add_module(name=serial_name, module=uart)

        # IRQ.
        if self.irq.enabled:
            self.irq.add(serial_name, use_loc_if_exists=True)

        return serial_name, getattr(self, serial_name)

    def _add_con_i2c(self, platform, port, sda, scl):
        pads = self.add_extension(
            platform, "i2c", port,
            Subsignal("sda", Pins(f"con{port}:{sda}")),
            Subsignal("scl", Pins(f"con{port}:{scl}")),
            IOStandard("LVCMOS33")
        )

        ## Add module
        i2c_name = f"i2c{port}"
        i2c = I2CMaster(pads)
        self.add_module(name=i2c_name, module=i2c)

        return i2c_name, i2c
    
    def add_con_gpio(self, platform, port, in_pads, out_pads):
        pads = self.add_extension(
            platform, "gpio", port,
            Subsignal("inputs", Pins(" ".join([f"con{port}:{x}" for x in in_pads]))),
            Subsignal("outputs", Pins(" ".join([f"con{port}:{x}" for x in out_pads]))),
            IOStandard("LVCMOS33")
        )

        len_con_gpio_in_pads_before = len(self._con_gpio_in_pads) if self._con_gpio_in_pads is not None else 0
        len_con_gpio_out_pads_before = len(self._con_gpio_out_pads) if self._con_gpio_out_pads is not None else 0
        self._con_gpio_in_pads = pads.inputs if self._con_gpio_in_pads is None else Cat(self._con_gpio_in_pads, pads.inputs)
        self._con_gpio_out_pads = pads.outputs if self._con_gpio_out_pads is None else Cat(self._con_gpio_out_pads, pads.outputs)

        # Return slice
        return (len_con_gpio_in_pads_before, len(self._con_gpio_in_pads)), (len_con_gpio_out_pads_before, len(self._con_gpio_out_pads))

    def add_con_di16(self, platform, port):
        self.logger.info(f"Port {port}: DI16")
        interrupt, reset = self.add_con_gpio(platform, port, [2], [3])
        i2c_name, _ = self._add_con_i2c(platform, port, 0, 1)
        self.add_module(f"con_di16_{port}", KTS1622(i2c_name, ("con_gpio_in", interrupt[0]), ("con_gpio_out", reset[0])))

    def add_con_do16(self, platform, port):
        self.logger.info(f"Port {port}: DO16")
        interrupt, reset = self.add_con_gpio(platform, port, [2], [3])
        i2c_name, _ = self._add_con_i2c(platform, port, 0, 1)
        self.add_module(f"con_do16_{port}", KTS1622(i2c_name, ("con_gpio_in", interrupt[0]), ("con_gpio_out", reset[0])))

    def get_fdtoverlays(self, board_name, ftdoverlays):
        # Generate content
        json_src = os.path.join("build", board_name, "csr.json")
        dts_dict = defaultdict(lambda: list())
        with open(json_src) as json_file:
            d = json.load(json_file)
            for name, obj in xdir(self, True):
                if hasattr(obj, "dts"):
                    order, content = obj.dts(name, d)
                    dts_dict[order].append(content)
        content = "".join(["".join(l) for _,l in sorted(dts_dict.items())])
        if len(content) == 0:
            return ftdoverlays

        # Write file
        dts = os.path.join("build", board_name, "{}_overlay.dts".format(board_name))
        dtb = os.path.join("build", board_name, "{}_overlay.dtb".format(board_name))

        with open(json_src) as json_file, open(dts, "w") as dts_file:
            dts_content = """/dts-v1/;
/plugin/;
{content}
""".format(content=content)
            dts_file.write(dts_content)

        subprocess.check_call(
            "dtc -@ -O dtb -o {} {}".format(dtb, dts), shell=True)
        return ftdoverlays + f" {dtb}"

    def __init__(self, *, toolchain="vivado", sys_clk_freq=100e6,
        debug           = False,
        with_etherbone  = False,
        with_ethernet   = False,
        with_led_chaser = False,
        eth_dynamic_ip  = False,
        eth_reset_time  = "10e-3",
        eth_ip          = "192.168.1.50",
        remote_ip       = None,
        con_config      = "X"*20,
        **kwargs):
        self.logger = logging.getLogger("MVE-HIL")

        platform = mve_hil.Platform(toolchain=toolchain)

        # CRG --------------------------------------------------------------------------------------
        with_dram = (kwargs.get("integrated_main_ram_size", 0) == 0)
        self.crg = _CRG(platform, sys_clk_freq, with_dram)

        # SoCCore ----------------------------------------------------------------------------------
        if debug:
            kwargs["uart_name"]     = "crossover"
            if kwargs.get("cpu_type", "vexriscv") == "vexriscv":
                kwargs["cpu_variant"] = kwargs.get("cpu_variant", "standard") + "+debug"
        if kwargs.get("uart_name", "") == "crossover":
            kwargs["with_uartbone"] = True
        #kwargs["csr_address_width"] = 15
        kwargs["csr_paging"] = 0x400
        kwargs["irq_n_irqs"] = 32
        SoCCore.__init__(self, platform, sys_clk_freq, ident = "LiteX SoC on MVE-HIL", **kwargs)

        # DDR3 SDRAM -------------------------------------------------------------------------------
        if not self.integrated_main_ram_size:
            self.ddrphy = s7ddrphy.A7DDRPHY(platform.request("ddram"),
                memtype      = "DDR3",
                nphases      = 4,
                sys_clk_freq = sys_clk_freq,
            )
            self.add_sdram("sdram",
                phy                     = self.ddrphy,
                module                  = NT5CC128M16(sys_clk_freq, "1:4"),
                l2_cache_size           = kwargs.get("l2_size", 8192),
                l2_cache_full_memory_we = (toolchain=="vivado"),
            )

        # Ethernet / Etherbone ---------------------------------------------------------------------
        if with_ethernet or with_etherbone:
            self.ethphy = LiteEthS7PHYRGMII(
                clock_pads      = self.platform.request("eth_clocks", 0),
                pads            = self.platform.request("eth", 0),
                hw_reset_cycles = math.ceil(float(eth_reset_time) * self.sys_clk_freq),
                clk_freq        = self.sys_clk_freq,
                rx_delay        = 1e-9,   # Already delayed by RXDLY on board: compensate clock path
                cm_type         = "PLL",  # Use PLL by default
            )
            self.ethphy.add_timing_constraints(platform, self.crg.cd_sys.clk)

            self.ethphy1 = LiteEthS7PHYRGMII(
                clock_pads      = self.platform.request("eth_clocks", 1),
                pads            = self.platform.request("eth", 1),
                hw_reset_cycles = math.ceil(float(eth_reset_time) * self.sys_clk_freq),
                clk_freq        = self.sys_clk_freq,
                rx_delay        = 1e-9,    # Already delayed by RXDLY on board: compensate clock path
                cm_type         = "MMCM",  # PLL is already used by ethphy
            )
            self.ethphy1.add_timing_constraints(platform, self.crg.cd_sys.clk)


            if with_etherbone:
                self.add_etherbone(
                    name="etherbone",
                    phy=self.ethphy,
                    ip_address=eth_ip,
                    with_ethmac=with_ethernet,
                    phy_cd="ethphy_eth"
            )
            if with_ethernet:
                self.add_ethernet(
                    name="ethmac",
                    phy=self.ethphy,
                    dynamic_ip=eth_dynamic_ip,
                    local_ip=eth_ip,
                    remote_ip=remote_ip,
                    with_timing_constraints=False,
                    phy_cd="ethphy_eth"
                )
                self.add_ethernet(
                    name="ethmac1",
                    phy=self.ethphy1,
                    with_timing_constraints=False,
                    phy_cd="ethphy1_eth"
                )

        # Leds -------------------------------------------------------------------------------------
        if with_led_chaser:
            self.leds_i2c = I2CMaster(
                pads = platform.request("leds_i2c")
            )
            self.leds = LedChaser(
                pads         = platform.request_all("som_led"),
                sys_clk_freq = sys_clk_freq)
            
        # Connectors -------------------------------------------------------------------------------
        self._con_gpio_in_pads = None
        self._con_gpio_out_pads = None

        assert len(con_config) == 20
        for i, c in enumerate(con_config):
            if c == 'C':
                fct = self.add_con_can2
            elif c == 'S':
                fct = self.add_con_rs
            elif c == 'I':
                fct = self.add_con_di16
            elif c == 'O':
                fct = self.add_con_do16
            elif c == 'X':
                continue
            else:
                assert False, f"Not supported configuration: {c}"
            fct(platform, i + 1)

        gpio = GPIOInOut(self._con_gpio_in_pads, self._con_gpio_out_pads, self.irq.enabled)
        self.add_module(name="con_gpio", module=gpio)
        if self.irq.enabled and hasattr(gpio, 'ev'):
            self.irq.add("con_gpio")

# Build --------------------------------------------------------------------------------------------

def main():
    from litex.build.parser import LiteXArgumentParser
    parser = LiteXArgumentParser(platform=mve_hil.Platform, description="LiteX SoC on MVE-HIL.")
    parser.add_target_argument("--flash",           action="store_true",       help="Flash bitstream.")
    parser.add_target_argument("--sys-clk-freq",    default=125e6, type=float, help="System clock frequency.")
    parser.add_target_argument("--debug",           action="store_true",       help="Enable debug features. (UART has to be used with the wishbone-tool.)")
    parser.add_target_argument("--with-led-chaser", action="store_true",       help="Enable led chaser.")
    parser.add_argument("--with-ethernet",          action="store_true",       help="Add Ethernet.")
    parser.add_argument("--with-etherbone",         action="store_true",       help="Add EtherBone.")
    parser.add_target_argument("--eth-ip",          default="192.168.1.50",    help="Ethernet/Etherbone IP address.")
    parser.add_target_argument("--remote-ip",       default="192.168.1.100",   help="Remote IP address of TFTP server.")
    parser.add_target_argument("--eth-dynamic-ip",  action="store_true",       help="Enable dynamic Ethernet IP addresses setting.")
    parser.add_target_argument("--eth-reset-time",  default="10e-3",           help="Duration of Ethernet PHY reset.")
    parser.add_argument("--with-sdcard",            action="store_true",       help="Enable SDCard support.")
    parser.add_target_argument("--con-config",      default="X"*20,            help="Connectors configuration.")
    parser.add_target_argument("--programmer-name", default="openocd",         help="Programmer name (vivado, openocd)")
    parser.add_target_argument("--jtag-config",     default="../prog/openocd_xc7_ktlink.cfg", help="Openocd configuration file")
    args = parser.parse_args()

    assert not (args.with_etherbone and args.eth_dynamic_ip)

    soc = BaseSoC(
        toolchain              = args.toolchain,
        debug                  = args.debug,
        sys_clk_freq           = args.sys_clk_freq,
        with_led_chaser        = args.with_led_chaser,
        with_ethernet          = args.with_ethernet,
        with_etherbone         = args.with_etherbone,
        eth_ip                 = args.eth_ip,
        remote_ip              = args.remote_ip,
        eth_dynamic_ip         = args.eth_dynamic_ip,
        eth_reset_time         = args.eth_reset_time,
        con_config             = args.con_config,
        **parser.soc_argdict
    )

    if args.with_sdcard:
        soc.add_sdcard(software_debug=False)

    builder = Builder(soc, **parser.builder_argdict)
    if builder.csr_svd is None:
        builder.csr_svd = os.path.join(builder.output_dir, "csr.svd")
    if args.build:
        builder.build(**parser.toolchain_argdict)

    if args.load:
        prog = soc.platform.create_programmer(args.programmer_name, args.jtag_config)
        prog.load_bitstream(builder.get_bitstream_filename(mode="sram"))

    if args.flash:
        prog = soc.platform.create_programmer(args.programmer_name, args.jtag_config)
        prog.flash(0, builder.get_bitstream_filename(mode="flash"))

if __name__ == "__main__":
    main()
