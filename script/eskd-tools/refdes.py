"""Reference designator prefixes per GOST 2.710-81 (table 1)."""

# per-file defaults for integrated circuits: DA analog, DD digital, DS memory
FILE_DEFAULT = {
    'ic-adc-dac-dds.SchLib': 'DA',
    'ic-amplifier.SchLib': 'DA',
    'ic-analog-interface.SchLib': 'DA',
    'ic-comparator.SchLib': 'DA',
    'ic-fpga.SchLib': 'DD',
    'ic-gate-driver.SchLib': 'DA',
    'ic-interface.SchLib': 'DD',
    'ic-logic.SchLib': 'DD',
    'ic-mcu.SchLib': 'DD',
    'ic-memory.SchLib': 'DS',
    'ic-power-controller.SchLib': 'DA',
    'ic-power-linear-reg.SchLib': 'DA',
    'ic-power-module.SchLib': 'DA',
    'ic-power-switchmode.SchLib': 'DA',
    'ic-power-voltage-references.SchLib': 'DA',
    'ic-sensor.SchLib': 'DA',
    'ic-сlock.SchLib': 'DD',
}

# per-component overrides: (file, libref) -> prefix
OVERRIDE = {
    # digital audio sample-rate converters
    ('ic-adc-dac-dds.SchLib', 'CT5302xL'): 'DD',
    ('ic-adc-dac-dds.SchLib', 'CT5302xN'): 'DD',
    ('ic-adc-dac-dds.SchLib', 'CT7302xL'): 'DD',
    # analog video OSD
    ('ic-interface.SchLib', 'AT7456'): 'DA',
    # analog multiplexer
    ('ic-logic.SchLib', '74HC4051D'): 'DA',
    # digital-output sensors
    ('ic-sensor.SchLib', 'ICM-42688-P'): 'DD',
    ('ic-sensor.SchLib', 'SPL06-001'): 'DD',
    ('ic-sensor.SchLib', 'LIS2DE12TR'): 'DD',
    ('ic-sensor.SchLib', 'MAX30102EFD+T'): 'DD',
    ('ic-sensor.SchLib', 'MAX30205MTA+_1'): 'DD',
    # discrete parts kept in IC libraries
    ('ic-sensor.SchLib', 'SMD0805-20'): 'VT',
    ('ic-power-module.SchLib', 'FF11MR12W1M1_B11'): 'VT',
    ('ic-power-module.SchLib', 'IM564X6DXKMA1'): 'VT',
    # connectors
    ('connector.SchLib', 'Jumper_one_double'): 'X',
    ('connector.SchLib', 'Jumper_one_single'): 'X',
    ('connector.SchLib', 'Jumper_two_single'): 'X',
    ('connector.SchLib', 'Solder_Pad'): 'X',
    ('connector.SchLib', 'Test_Point_Connector'): 'XT',
    ('connector.SchLib', 'Test_Point_Pad'): 'XT',
    # electromechanics
    ('electromechanics.SchLib', 'Arrester_2E'): 'FV',
    ('electromechanics.SchLib', 'Arrester_3E'): 'FV',
    ('electromechanics.SchLib', 'Button_tactile_SMD'): 'SB',
    ('electromechanics.SchLib', 'Button_tactile_THD'): 'SB',
    ('electromechanics.SchLib', 'Buzzer'): 'HA',
    ('electromechanics.SchLib', 'Encoder_PEC12'): 'SA',
    ('electromechanics.SchLib', 'Switch_DPDT'): 'SA',
    ('electromechanics.SchLib', 'Switch_SPST_4_ways'): 'SA',
    # filters
    ('capacitor.SchLib', 'EMI_LC_Combined'): 'Z',
    ('inductor.SchLib', 'EMI_MURATA_BNX'): 'Z',
    ('inductor.SchLib', 'Ferrite_beads'): 'L',
    # quartz resonators
    ('oscilator.SchLib', 'Crystal_2p'): 'ZQ',
    ('oscilator.SchLib', 'Crystal_4p'): 'ZQ',
}

WHOLE_FILE = {
    'batteries.SchLib': 'GB',
}

MODULE_CONVERTER_WORDS = ('DC/DC', 'AC/DC', 'converter', 'flyback')


def prefix(fname, libref, current, descr):
    key = (fname, libref)
    if key in OVERRIDE:
        return OVERRIDE[key]
    if fname in WHOLE_FILE:
        return WHOLE_FILE[fname]
    if fname == 'module.SchLib' and current.startswith('D'):
        # converters are "U" (electrical-to-electrical converters), other modules "A" (devices)
        return 'U' if any(w.lower() in (descr or '').lower() for w in MODULE_CONVERTER_WORDS) else 'A'
    if fname in FILE_DEFAULT and current.rstrip('?') in ('D', 'DA', 'DD', 'U'):
        return FILE_DEFAULT[fname]
    return None
