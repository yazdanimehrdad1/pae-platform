export const mockAssetTree = {
    "Site Alpha": {
        "Substation A": {
            "Transformer T1": [
                "Real Power (MW)",
                "Reactive Power (MVAR)",
                "Apparent Power (MVA)",
                "Current IA",
                "Current IB",
                "Current IC",
                "Voltage VA",
                "Voltage VB",
                "Voltage VC",
                "Temperature"
            ],
            "Feeder F1": [
                "Real Power (kW)",
                "Reactive Power (kVAR)",
                "Current IA",
                "Current IB",
                "Current IC",
                "Power Factor"
            ],
            "Protection P1": ["Status", "Fault Current", "Trip Count"]
        },
        "Substation B": {
            "Transformer T2": [
                "Real Power (MW)",
                "Reactive Power (MVAR)",
                "Apparent Power (MVA)",
                "Current IA",
                "Current IB",
                "Current IC",
                "Temperature"
            ],
            "Generator G1": [
                "Real Power Output (MW)",
                "Reactive Power Output (MVAR)",
                "Voltage Output",
                "Frequency (Hz)",
                "RPM",
                "Fuel Level"
            ]
        }
    }
};

export const mockMetadata = {
    identification: {
        "Asset ID": "TXF-001-A",
        "Make": "ABB",
        "Model": "TXF-150MVA",
        "Serial": "TX150-2023-001"
    },
    electrical: {
        "Rated Power": "150 MVA",
        "Primary Voltage": "132 kV",
        "Secondary Voltage": "11 kV",
        "Connection": "Dyn11"
    },
    integration: {
        "Protocol": "IEC 61850",
        "IP Address": "192.168.1.100",
        "Last Update": "2024-01-15 14:30:22",
        "Communication": "Online"
    }
};
