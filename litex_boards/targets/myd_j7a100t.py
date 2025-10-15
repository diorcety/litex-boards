#!/usr/bin/env python3
#
# This file is part of LiteX-Boards.
#
# Copyright (c) 2021 Antmicro <www.antmicro.com>
# Copyright (c) 2022 IBM Corp.
# SPDX-License-Identifier: BSD-2-Clause


import math

from migen import *

from litex.gen import *

from litex_boards.platforms import myd_j7a100t

from litex.soc.cores.clock import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.cores.led import LedChaser

from litedram.modules import NT5CC128M16
from litedram.phy import s7ddrphy

from liteeth.phy import LiteEthS7PHYRGMII
from liteeth.phy.a7_1000basex import A7_1000BASEX
from liteeth.phy.a7_gtp import QPLL, QPLLSettings

from litepcie.phy.s7pciephy import S7PCIEPHY

# CRG ----------------------------------------------------------------------------------------------

class _CRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq, with_dram):
        self.rst       = Signal()
        self.cd_sys    = ClockDomain()
        if with_dram:
            self.cd_sys4x     = ClockDomain()
            self.cd_sys4x_dqs = ClockDomain()
            self.cd_idelay    = ClockDomain()
                
        # Clk / Rst
        clk200 = platform.request("clk200")
        rst_n  = platform.request("rst_n", 0)

        # PLL.
        self.pll = pll = S7PLL(speedgrade=-2)
        self.comb += pll.reset.eq(~rst_n | self.rst)
        pll.register_clkin(clk200, 200e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)
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
    def __init__(self, *, toolchain="vivado", sys_clk_freq=125e6,
        debug           = False,
        with_pcie       = False,
        with_etherbone  = False,
        with_ethernet   = False,
        with_led_chaser = False,
        eth_dynamic_ip  = False,
        eth_reset_time  = "10e-3",
        eth_ip          = "192.168.1.50",
        remote_ip       = None,
        **kwargs):
        platform = myd_j7a100t.Platform(toolchain=toolchain)

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
        SoCCore.__init__(self, platform, sys_clk_freq, ident = "LiteX SoC on MYD-J7A100T", **kwargs)

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

        # PCIe -------------------------------------------------------------------------------------
        if with_pcie:
            qpll_pcie_settings = None
            self.pcie_phy = S7PCIEPHY(platform, platform.request("pcie_x2"),
                data_width = 64,
                bar0_size  = 0x20000)
            self.add_pcie(phy=self.pcie_phy, ndmas=1)

        if with_ethernet or with_etherbone:
            refclk125 = self.platform.request("clk125")
            refclk125_se = Signal()
            self.specials += Instance("IBUFDS_GTE2",
                    i_CEB = 0,
                    i_I   = refclk125.p,
                    i_IB  = refclk125.n,
                    o_O   = refclk125_se,
                )

        if with_ethernet or with_etherbone or with_pcie:
            qpll_eth_settings = QPLLSettings(
                refclksel  = 0b001,
                fbdiv      = 4,
                fbdiv_45   = 5,
                refclk_div = 1,
            )

            # Shared QPLL.
            self.qpll = qpll = QPLL(
                gtrefclk0     = Open() if not with_pcie else self.pcie_phy.pcie_refclk,
                qpllsettings0 = None   if not with_pcie else qpll_pcie_settings,
                gtrefclk1     = Open() if not (with_ethernet or with_etherbone) else refclk125_se,
                qpllsettings1 = None   if not (with_ethernet or with_etherbone) else qpll_eth_settings,
            )
            self.submodules += qpll

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

            self.ethphy2 = A7_1000BASEX(
                qpll_channel = qpll.channels[1],
                data_pads    = self.platform.request("sfp", 0),
                sys_clk_freq = self.clk_freq,
                tx_cm_type   = "PLL",  # Use PLL by default
                rx_cm_type   = "PLL",  # Use PLL by default
            )

            self.ethphy3 = A7_1000BASEX(
                qpll_channel = qpll.channels[1],
                data_pads    = self.platform.request("sfp", 1),
                sys_clk_freq = self.clk_freq,
                tx_cm_type   = "MMCM",  # PLL is already used by ethphy2
                rx_cm_type   = "MMCM",  # PLL is already used by ethphy2
            )

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
                self.add_ethernet(
                    name="ethmac2",
                    phy=self.ethphy2,
                    with_timing_constraints=True,
                    phy_cd="ethphy2_eth"
                )
                self.add_ethernet(
                    name="ethmac3",
                    phy=self.ethphy3,
                    with_timing_constraints=True,
                    phy_cd="ethphy3_eth"
                )

        # Leds -------------------------------------------------------------------------------------
        if with_led_chaser:
            self.leds = LedChaser(
                pads         = Cat(platform.request_all("baseboard_led"), platform.request_all("som_led")),
                sys_clk_freq = sys_clk_freq)

# Build --------------------------------------------------------------------------------------------

def main():
    from litex.build.parser import LiteXArgumentParser
    parser = LiteXArgumentParser(platform=myd_j7a100t.Platform, description="LiteX SoC on MYD-J7A100T.")
    parser.add_target_argument("--flash",           action="store_true",       help="Flash bitstream.")
    parser.add_target_argument("--sys-clk-freq",    default=125e6, type=float, help="System clock frequency.")
    parser.add_target_argument("--debug",           action="store_true",       help="Enable debug features. (UART has to be used with the wishbone-tool.)")
    parser.add_target_argument("--with-led-chaser", action="store_true",       help="Enable led chaser.")
    parser.add_target_argument("--with-pcie",       action="store_true",       help="Add PCIe.")
    parser.add_argument("--with-ethernet",          action="store_true",       help="Add Ethernet.")
    parser.add_argument("--with-etherbone",         action="store_true",       help="Add EtherBone.")
    parser.add_target_argument("--eth-ip",          default="192.168.1.50",    help="Ethernet/Etherbone IP address.")
    parser.add_target_argument("--remote-ip",       default="192.168.1.100",   help="Remote IP address of TFTP server.")
    parser.add_target_argument("--eth-dynamic-ip",  action="store_true",       help="Enable dynamic Ethernet IP addresses setting.")
    parser.add_target_argument("--eth-reset-time",  default="10e-3",           help="Duration of Ethernet PHY reset.")
    parser.add_argument("--with-sdcard",            action="store_true",       help="Enable SDCard support.")
    parser.add_target_argument("--programmer-name", default="openocd",         help="Programmer name (vivado, openocd)")
    parser.add_target_argument("--jtag-config",     default="../prog/openocd_xc7_ktlink.cfg", help="Openocd configuration file")
    args = parser.parse_args()

    assert not (args.with_etherbone and args.eth_dynamic_ip)

    soc = BaseSoC(
        toolchain              = args.toolchain,
        debug                  = args.debug,
        sys_clk_freq           = args.sys_clk_freq,
        with_led_chaser        = args.with_led_chaser,
        with_pcie              = args.with_pcie,
        with_ethernet          = args.with_ethernet,
        with_etherbone         = args.with_etherbone,
        eth_ip                 = args.eth_ip,
        remote_ip              = args.remote_ip,
        eth_dynamic_ip         = args.eth_dynamic_ip,
        eth_reset_time         = args.eth_reset_time,
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
