#
# This file is part of LiteX-Boards.
#
# SPDX-License-Identifier: BSD-2-Clause

from litex.build.generic_platform import *
from litex.build.xilinx import Xilinx7SeriesPlatform, VivadoProgrammer
from litex.build.openocd import OpenOCD

# This board is available here:
# https://www.myirtech.com/list.asp?id=765

# IOs ----------------------------------------------------------------------------------------------

_io = [
    #
    # SOM
    #
    # CLK
    (
        "clk200",
        0,
        Subsignal("p", Pins("R4"), IOStandard("DIFF_SSTL15")),  # sys_clk_p
        Subsignal("n", Pins("T4"), IOStandard("DIFF_SSTL15")),  # sys_clk_n
    ),
    # DDR3 SDRAM
    (
        "ddram",
        0,
        Subsignal(
            "a",
            Pins("V2 Y4 Y3 AB5 AB3 AA4 AA1 AA3 AB1 W2 W5 W1 AB6 Y2"),  # Y1 Y6 not used
            IOStandard("SSTL15"),
        ),
        Subsignal("ba", Pins("AA5 W4 AB7"), IOStandard("SSTL15")),
        Subsignal("ras_n", Pins("Y8"), IOStandard("SSTL15")),
        Subsignal("cas_n", Pins("AA8"), IOStandard("SSTL15")),
        Subsignal("we_n", Pins("AA6"), IOStandard("SSTL15")),
        Subsignal("cs_n", Pins("Y7"), IOStandard("SSTL15")),
        Subsignal("dm", Pins("M6 J4 H2 B1"), IOStandard("SSTL15")),
        Subsignal(
            "dq",
            Pins(
                "R1 M5 P2 P6 N4 N5 N2 P1",
                "L5 K3 K6 J6 M2 L3 M3 L4",
                "G4 G3 J5 H3 H4 K1 H5 G2",
                "E2 A1 G1 B2 F1 C2 F3 D2",
            ),
            IOStandard("SSTL15"),
            Misc("IN_TERM=UNTUNED_SPLIT_50"),
        ),
        Subsignal("dqs_p", Pins("P5 M1 K2 E1"), IOStandard("DIFF_SSTL15")),
        Subsignal("dqs_n", Pins("P4 L1 J2 D1"), IOStandard("DIFF_SSTL15")),
        Subsignal(
            "clk_p",
            Pins("T5"),
            IOStandard("DIFF_SSTL15"),
            Misc("IO_BUFFER_TYPE=NONE"),  # 200M_CLOCK
        ),
        Subsignal(
            "clk_n",
            Pins("U5"),
            IOStandard("DIFF_SSTL15"),
            Misc("IO_BUFFER_TYPE=NONE"),  # 200M_CLOCK
        ),
        Subsignal("cke", Pins("Y9"), IOStandard("SSTL15")),
        Subsignal("odt", Pins("AB8"), IOStandard("SSTL15")),
        Subsignal("reset_n", Pins("AB2"), IOStandard("LVCMOS15")),
        Misc("SLEW=FAST"),
    ),
    # Led
    ("som_led", 0, Pins("V7"), IOStandard("LVCMOS15")),  # USER_LED
    # SPIFlash
    (
        "spiflash4x",
        0,
        Subsignal("cs_n", Pins("T19")),  #             QSPI_CS
        Subsignal("dq",   Pins("P22 R22 P21 R21")),  # QSPI_D0-3
        IOStandard("LVCMOS33"),
    ),
    # I2C EEPROM
    (
        "eeprom",
        0,
        Subsignal("scl", Pins("K17"), Misc("PULLUP true")),  # EEPROM_SCL
        Subsignal("sda", Pins("J17"), Misc("PULLUP true")),  # EEPROM_SDA
        IOStandard("LVCMOS33"),
    ),
    #
    # Dev board
    #
    # CLKS
    (
        "clk100",
        0,
        Subsignal("p", Pins("F6"), IOStandard("DIFF_SSTL12")),  # MGTP_B216_REF_CLK_P0
        Subsignal("n", Pins("E6"), IOStandard("DIFF_SSTL12")),  # MGTP_B216_REF_CLK_N0
    ),
    (
        "clk125",
        0,
        Subsignal("p", Pins("F10"), IOStandard("DIFF_SSTL12")),  # MGTP_B216_REF_CLK_P1
        Subsignal("n", Pins("E10"), IOStandard("DIFF_SSTL12")),  # MGTP_B216_REF_CLK_N1
    ),
    # Leds
    ("baseboard_led", 0, Pins("H15"), IOStandard("LVCMOS33")),  # LED0
    ("baseboard_led", 1, Pins("J15"), IOStandard("LVCMOS33")),  # LED1
    # Switches
    ("user_sw", 0, Pins("P17"), IOStandard("LVCMOS33")),  # KEY_0
    ("user_sw", 1, Pins("N17"), IOStandard("LVCMOS33")),  # KEY_1
    ("rst_n", 0, Pins("P15"), IOStandard("LVCMOS33")),  # KEY_2
    # Serial Debug
    (
        "serial",
        0,
        Subsignal("tx", Pins("T18")),  # DEBUG_TXD
        Subsignal("rx", Pins("R18")),  # DEBUG_RXD
        IOStandard("LVCMOS33"),
    ),
    # SDCard
    (
        "sdcard",
        0,
        Subsignal("clk", Pins("V20")),  #              CLK
        Subsignal("cmd", Pins("Y21")),  #              CMD
        Subsignal("data", Pins("P19 R19 U17 U18")),  # DAT0-3
        Subsignal("cd", Pins("AA19")),  #              CD
        IOStandard("LVCMOS33"),
    ),
    # CSI
    (
        "csi",
        0,
        Subsignal("scl", Pins("B16")),  #                          I2C_SCL
        Subsignal("sda", Pins("B15")),  #                           I2C_SDA
        Subsignal("rst", Pins("G21")),  #                           CAM_RST
        Subsignal("pwrdn", Pins("G22")),  #                         CAM_PWRDN
        Subsignal("vsync", Pins("B17")),  #                         CAM_VSYNC
        Subsignal("hsync", Pins("B18")),  #                         CAM_HSYNC
        Subsignal("xclk", Pins("E19")),  #                          XCLK
        Subsignal("pclk", Pins("D19")),  #                          CAM_PCLK
        Subsignal("d", Pins("C22 B21 A21 B22 D21 E21 E18 F18")),  # CAM_DATA0-7
        IOStandard("LVCMOS33"),
    ),
    # HDMI out
    (
        "hdmi_out",
        0,
        Subsignal("r", Pins("L18 M18 N18 N19 N20 M20 K13 K14")),  # HDMI_R0-7_OUT
        Subsignal("g", Pins("H17 H18 J22 H22 H20 G20 K21 K22")),  # HDMI_G0-7_OUT
        Subsignal("b", Pins("H13 G13 G15 G16 J14 H14 G17 G18")),  # HDMI_B0-7_OUT
        Subsignal("scl", Pins("K19")),  #                           HDMI_SCL_OUT
        Subsignal("sda", Pins("K20")),  #                           HDMI_SDA_OUT
        Subsignal("rst", Pins("K18")),  #                           HDMI_RST_OUT
        Subsignal("int", Pins("K19")),  #                           HDMI_TP_INTn_OUT
        Subsignal("vsync", Pins("J20")),  #                         HDMI_VSYNC_OUT
        Subsignal("hsync", Pins("J19")),  #                         HDMI_HSYNC_OUT
        Subsignal("de", Pins("H19")),  #                            HDMI_DE_OUT
        Subsignal("idclk", Pins("J21")),  #                         HDMI_IDCLK_OUT
        IOStandard("LVCMOS33"),
    ),
    # HDMI in
    (
        "hdmi_in",
        0,
        Subsignal("r", Pins("A13 A14 B20 A20 A18 A19 D20 C20")),  # HDMI_R0-7
        Subsignal("g", Pins("E13 E14 D14 D15 C13 B13 A15 A16")),  # HDMI_G0-7
        Subsignal("b", Pins("F13 F14 F16 E17 C14 C15 E16 D16")),  # HDMI_B0-7
        Subsignal("scl", Pins("E22")),  #                           HDMI_SCL
        Subsignal("sda", Pins("D22")),  #                           HDMI_SDA
        Subsignal("rst", Pins("F15")),  #                           HDMI_RST
        Subsignal("int", Pins("F21")),  #                           HDMI_INT_IN
        Subsignal("vsync", Pins("D12")),  #                         HDMI_VSYNC
        Subsignal("hsync", Pins("C17")),  #                         HDMI_HSYNC
        Subsignal("de", Pins("C18")),  #                            HDMI_DE
        Subsignal("idclk", Pins("C19")),  #                         HDMI_IDCLK
        IOStandard("LVCMOS33"),
    ),
    # RGMII Ethernet
    (
        "eth_clocks",
        0,
        Subsignal("tx", Pins("W20")),  # ETH1_RGMII_TX_CLK
        Subsignal("rx", Pins("W19")),  # ETH1_RGMII_RX_CLK
        IOStandard("LVCMOS33"),
    ),
    (
        "eth_clocks",
        1,
        Subsignal("tx", Pins("Y19")),  # ETH2_RGMII_TX_CLK
        Subsignal("rx", Pins("Y18")),  # ETH2_RGMII_RX_CLK
        IOStandard("LVCMOS33"),
    ),
    (
        "eth",
        0,
        Subsignal("rst_n",   Pins("Y22")),  #              ETH1_RESET_N
        Subsignal("mdio",    Pins("V17")),  #              ETH1_MDIO
        Subsignal("mdc",     Pins("W17")),  #              ETH1_MDC
        Subsignal("rx_ctl",  Pins("V18")),  #              ETH1_RGMII_RX_DV
        Subsignal("rx_data", Pins("U22 V22 T21 U21")),  #  ETH1_RGMII_RXD0-3
        Subsignal("tx_ctl",  Pins("U20")),  #              ETH1_RGMII_TX_EN
        Subsignal("tx_data", Pins("W21 W22 AA20 AA21"),  # ETH1_RGMII_TXD0-3
        ),
        IOStandard("LVCMOS33"),
    ),
    (
        "eth",
        1,
        Subsignal("rst_n",   Pins("AB20")),  #                ETH2_RESET_N
        Subsignal("mdio",    Pins("P14")),  #                 ETH2_MDIO
        Subsignal("mdc",     Pins("R14")),  #                 ETH2_MDC
        Subsignal("rx_ctl",  Pins("V19")),  #                 ETH2_RGMII_RX_DV
        Subsignal("rx_data", Pins("AB21 AB22 AA18 AB18")),  # ETH2_RGMII_RXD0-3
        Subsignal("tx_ctl" , Pins("P20")),  #                 ETH2_RGMII_TX_EN
        Subsignal("tx_data", Pins("N13 N14 P16 R17")),  #     ETH2_RGMII_TXD0-3
        IOStandard("LVCMOS33"),
    ),
    # SFP
    (
        "sfp_a",
        0,  # SFP A
        Subsignal("txp", Pins("B6")),  #  MGTP_B216_TX_P2
        Subsignal("txn", Pins("A6")),  #  MGTP_B216_TX_N2
        Subsignal("rxp", Pins("B10")),  # MGTP_B216_RX_P2
        Subsignal("rxn", Pins("A10")),  # MGTP_B216_RX_N2
    ),
    (
        "sfp_a_tx",
        0,  # SFP A
        Subsignal("p", Pins("B6")),  # MGTP_B216_TX_P2
        Subsignal("n", Pins("A6")),  # MGTP_B216_TX_N2
    ),
    (
        "sfp_a_rx",
        0,  # SFP A
        Subsignal("p", Pins("B10")),  # MGTP_B216_RX_P2
        Subsignal("n", Pins("A10")),  # MGTP_B216_RX_N2
    ),
    (
        "sfp_b",
        0,  # SFP B
        Subsignal("txp", Pins("D7")),  # MGTP_B216_TX_P3
        Subsignal("txn", Pins("C7")),  # MGTP_B216_TX_N3
        Subsignal("rxp", Pins("D9")),  # MGTP_B216_RX_P3
        Subsignal("rxn", Pins("C9")),  # MGTP_B216_RX_N3
    ),
    (
        "sfp_b_tx",
        0,  # SFP B
        Subsignal("p", Pins("D7")),  # MGTP_B216_TX_P3
        Subsignal("n", Pins("C7")),  # MGTP_B216_TX_N3
    ),
    (
        "sfp_b_rx",
        0,  # SFP B
        Subsignal("p", Pins("D9")),  # MGTP_B216_RX_P3
        Subsignal("n", Pins("C9")),  # MGTP_B216_RX_N3
    ),
    # PCIe
    (
        "pcie_x1",
        0,
        Subsignal("rst_n", Pins("R16"), IOStandard("LVCMOS33"), Misc("PULLUP=TRUE")),  # PCIE_RST
        Subsignal("clk_p", Pins("F6")),  #                          REFCLK+
        Subsignal("clk_n", Pins("E6")),  #                          REFCLK-
        Subsignal("rx_p", Pins("B8")),  #                           PETP0
        Subsignal("rx_n", Pins("A8")),  #                           PETN0
        Subsignal("tx_p", Pins("B4")),  #                           PERP0
        Subsignal("tx_n", Pins("A4")),  #                           PERN0
    ),
    (
        "pcie_x2",
        0,
        Subsignal("rst_n", Pins("R16"), IOStandard("LVCMOS33"), Misc("PULLUP=TRUE")),  # PCIE_RST
        Subsignal("clk_p", Pins("F6")),  #                          REFCLK+
        Subsignal("clk_n", Pins("E6")),  #                          REFCLK-
        Subsignal("rx_p", Pins("B8 D11")),  #                       PETP0-1
        Subsignal("rx_n", Pins("A8 C11")),  #                       PETN0-1
        Subsignal("tx_p", Pins("B4 D5")),  #                        PERP0-1
        Subsignal("tx_n", Pins("A4 C5")),  #                        PERN0-1
    ),
]

# Connectors ---------------------------------------------------------------------------------------

_connectors = [
    (
        "IO-EXP",
        {
            1: "---",  #   VCC_3V3
            2: "---",  #   VCC_5V
            3: "V10",  #   IO_B13_LP_10
            4: "---",  #   VCC_5V
            5: "W10",  #   IO_B13_LN_10
            6: "---",  #   GND
            7: "Y11",  #   IO_B13_LP_11
            8: "Y12",  #   IO_B13_LN_11
            9: "---",  #   GND
            10: "W11",  #  IO_B13_LP_12
            11: "V13",  #  IO_B13_LP_13
            12: "W12",  #  IO_B13_LN_12
            13: "V14",  #  IO_B13_LN_13
            14: "---",  #  GND
            15: "U15",  #  IO_B13_LP_14
            16: "Y13",  #  IO_B13_LP_5
            17: "---",  #  VCC_3V3
            18: "AA14",  # IO_B13_LN_5
            19: "V15",  #  IO_B13_LN_14
            20: "---",  #  GND
            21: "T14",  #  IO_B13_LP_15
            22: "Y16",  #  IO_B13_LP_1
            23: "T15",  #  IO_B13_LN_15
            24: "AA16",  # IO_B13_LN_1
            25: "---",  #  GND
            26: "W14",  #  IO_B13_LP_6
            27: "W15",  #  IO_B13_LP_16
            28: "Y14",  #  IO_B13_LN_6
            29: "W16",  #  IO_B13_LN_16
            30: "---",  #  GND
            31: "T16",  #  IO_B13_LP_17
            32: "AA13",  # IO_B13_LP_3
            33: "U16",  #  IO_B13_LN_17
            34: "---",  #  GND
            35: "AB16",  # IO_B13_LP_2
            36: "AB13",  # IO_B13_LN_3
            37: "AB17",  # IO_B13_LN_2
            38: "AA15",  # IO_B13_LP_4
            39: "---",  #  GND
            40: "AB15",  # IO_B13_LN_4
        },
    ),
]
# Platform -----------------------------------------------------------------------------------------


class Platform(Xilinx7SeriesPlatform):
    default_clk_name = "clk200"
    default_clk_period = 1e9 / 200e6

    def __init__(self, toolchain="vivado"):
        Xilinx7SeriesPlatform.__init__(
            self, "xc7a100tfgg484-2", _io, _connectors, toolchain=toolchain
        )
        self.toolchain.bitstream_commands = \
            [
                "set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]",
                "set_property CONFIG_MODE SPIx4 [current_design]",
                "set_property BITSTREAM.CONFIG.CONFIGRATE 50 [current_design]",
            ]
        self.toolchain.additional_commands = \
            ["write_cfgmem -force -format bin -interface spix4 -size 16 "
             "-loadbit \"up 0x0 {build_name}.bit\" -file {build_name}.bin"]
        self.add_platform_command("set_property CFGBVS VCCO [current_design]")
        self.add_platform_command("set_property CONFIG_VOLTAGE 3.3 [current_design]")

    def create_programmer(self, name="vivado", openocd_cfg="../prog/openocd_xc7_ktlink.cfg"):
        if name == "vivado":
            return VivadoProgrammer(flash_part='mx25l25673g-spi-x1_x2_x4')
        elif name == "openocd":
            bscan_spi = "bscan_spi_xc7a100t.bit"
            return OpenOCD(openocd_cfg, bscan_spi)
        else:
            raise Exception(f"Unsupported programmer: {name}")

    def do_finalize(self, fragment):
        Xilinx7SeriesPlatform.do_finalize(self, fragment)
        self.add_period_constraint(
            self.lookup_request("clk200", loose=True), 1e9 / 200e6
        )
