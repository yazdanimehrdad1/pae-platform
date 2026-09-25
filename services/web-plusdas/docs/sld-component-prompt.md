# Single Line Diagram (SLD) Component - Implementation Guide

## Overview

This document provides a comprehensive guide for implementing a Single Line Diagram (SLD) component for a microgrid power system visualization. The SLD displays electrical devices, buses, and connections in a hierarchical top-to-bottom layout with animated power flow indicators.

## Architecture

### Component Structure

The SLD system consists of the following components:

1. **MicrogridSLD** (`src/components/sld/MicrogridSLD.tsx`) - Main container component
2. **SLDNode** (`src/components/sld/SLDNode.tsx`) - Individual device/node component
3. **BusBar** (`src/components/sld/BusBar.tsx`) - Bus bar visualization component
4. **ConnectionLine** (`src/components/sld/ConnectionLine.tsx`) - Animated connection line component
5. **types.ts** (`src/components/sld/types.ts`) - TypeScript type definitions

### Data Structure

The SLD is driven by a JSON data structure that defines devices, connections, buses, and summary information.

#### Type Definitions

```typescript
interface SLDDevice {
  id: string;
  type: "grid" | "bus" | "transformer" | "breaker" | "pv" | "bess" | "generator" | "load";
  name: string;
  voltage: string;
  status: "online" | "warning" | "offline";
  power?: string;
  powerFlow?: {
    direction: "export" | "import" | "generate" | "consume" | "charge" | "discharge";
    valueKW: number;
  };
  properties?: Record<string, unknown>;
  position?: {
    level: number; // Vertical level (0 = top)
    branch?: number; // Horizontal branch index (0 = leftmost)
  };
}

interface SLDConnection {
  from: string; // Device or Bus ID
  to: string; // Device or Bus ID
  flowDirection?: "down" | "up" | "left" | "right";
}

interface SLDBus {
  id: string;
  label: string;
  voltage: string;
  level: number;
  width?: string; // Tailwind CSS width class
}

interface SLDSummary {
  label: string;
  value: string;
  subtext: string;
  color?: string; // Tailwind CSS color class
}

interface SLDData {
  siteId?: string;
  siteName?: string;
  devices: SLDDevice[];
  connections: SLDConnection[];
  buses: SLDBus[];
  summary?: SLDSummary[];
}
```

#### JSON Example Structure

```json
{
  "siteId": "site-001",
  "siteName": "Main Microgrid Site",
  "devices": [
    {
      "id": "grid-1",
      "type": "grid",
      "name": "Utility Grid",
      "voltage": "13.8 kV",
      "status": "online",
      "power": "13.8 kV",
      "powerFlow": {
        "direction": "import",
        "valueKW": 150
      },
      "position": {
        "level": 0,
        "branch": 0
      }
    },
    {
      "id": "transformer-1",
      "type": "transformer",
      "name": "Main Transformer",
      "voltage": "13.8/0.48 kV",
      "status": "online",
      "power": "13.8/0.48 kV",
      "properties": {
        "capacity": "1000 kVA"
      },
      "position": {
        "level": 1,
        "branch": 0
      }
    },
    {
      "id": "pv-1",
      "type": "pv",
      "name": "Solar PV",
      "voltage": "480V",
      "status": "online",
      "power": "75 kW",
      "powerFlow": {
        "direction": "generate",
        "valueKW": 75
      },
      "properties": {
        "capacity": "100 kWp"
      },
      "position": {
        "level": 3,
        "branch": 0
      }
    },
    {
      "id": "bess-1",
      "type": "bess",
      "name": "Battery ESS",
      "voltage": "480V",
      "status": "warning",
      "power": "± 50 kW",
      "powerFlow": {
        "direction": "charge",
        "valueKW": 50
      },
      "properties": {
        "capacity": "200 kWh",
        "soc": 68
      },
      "position": {
        "level": 3,
        "branch": 2
      }
    }
  ],
  "connections": [
    {
      "from": "grid-1",
      "to": "transformer-1",
      "flowDirection": "down"
    },
    {
      "from": "transformer-1",
      "to": "main-bus",
      "flowDirection": "down"
    },
    {
      "from": "main-bus",
      "to": "pv-1",
      "flowDirection": "up"
    },
    {
      "from": "main-bus",
      "to": "bess-1",
      "flowDirection": "down"
    },
    {
      "from": "main-bus",
      "to": "load-bus",
      "flowDirection": "down"
    }
  ],
  "buses": [
    {
      "id": "main-bus",
      "label": "MAIN BUS",
      "voltage": "480V",
      "level": 2,
      "width": "w-[90%] max-w-[700px]"
    },
    {
      "id": "load-bus",
      "label": "LOAD BUS",
      "voltage": "480V",
      "level": 4,
      "width": "w-[60%] max-w-[500px]"
    }
  ],
  "summary": [
    {
      "label": "Total Generation",
      "value": "120 kW",
      "subtext": "Solar + Wind",
      "color": "text-accent"
    }
  ]
}
```

## Layout Requirements

### Hierarchical Structure

The SLD uses a **top-to-bottom hierarchical layout** with the following rules:

1. **Levels**: Devices and buses are positioned at specific vertical levels (0 = top, increasing downward)
2. **Branches**: Devices at the same level can be positioned horizontally using branch indices (0 = leftmost)
3. **Bus Placement**: Buses are positioned at their specified level and span horizontally
4. **Connection Rules**:
   - Only ONE connection line between any two elements (no duplicates)
   - Connections are explicitly defined in the `connections` array
   - Flow direction is determined by the connection's `flowDirection` or calculated from device levels

### Standard Layout Pattern

The typical microgrid structure follows this pattern:

- **Level 0**: Utility Grid
- **Level 1**: Main Transformer
- **Level 2**: Main Bus (480V)
- **Level 3**: DERs (Solar PV, Wind, Battery ESS) - connected to Main Bus
- **Level 4**: Load Bus (480V) - connected to Main Bus
- **Level 5**: Loads (Critical, Commercial, Residential) - connected to Load Bus

**Critical Rule**: There must be a bus between the Main Transformer and the DERs (Solar PV, Wind, BESS). The Main Bus should be at level 2, positioned between the transformer (level 1) and the DERs (level 3).

## Component Implementation Details

### 1. MicrogridSLD Component

**Location**: `src/components/sld/MicrogridSLD.tsx`

**Key Features**:
- Accepts `SLDData` as a prop
- Groups devices by level for rendering
- Renders devices, buses, and connections in hierarchical order
- Tracks rendered connections to prevent duplicates
- Handles bus-to-bus, device-to-device, and bus-to-device connections

**Rendering Logic**:
1. Group all devices by their `position.level`
2. Collect all levels (devices + buses) and sort them
3. For each level:
   - Render incoming connections to devices (device-to-device only)
   - Render devices at that level (sorted by branch index)
   - Render outgoing connections from devices (device-to-device only)
   - Render bus (if exists at this level) with connections to/from it
4. Render summary cards at the bottom

**Connection Rendering Rules**:
- Device-to-device connections: Rendered before/after device nodes
- Bus connections: Rendered before/after bus bars
- Each connection renders only once (tracked via `renderedConnections` Set)
- Flow direction determined by `flowDirection` property or calculated from device levels

### 2. SLDNode Component

**Location**: `src/components/sld/SLDNode.tsx`

**Props**:
```typescript
interface SLDNodeProps {
  title: string;
  icon: ReactNode;
  power?: string;
  status?: "online" | "warning" | "offline";
  variant?: "grid" | "solar" | "wind" | "battery" | "load" | "transformer";
  className?: string;
  children?: ReactNode;
}
```

**Visual Design**:
- Card-based design with border and background
- Status badge in top-right corner
- Device icon on the left
- Device name and voltage displayed
- Power flow information (if available)
- Special handling for BESS (shows SOC progress bar)
- Variant-specific styling (grid, solar, wind, battery, transformer, load)

**Status Colors**:
- `online`: Green background with green text
- `warning`: Yellow/amber background with yellow text
- `offline`: Red background with red text

### 3. BusBar Component

**Location**: `src/components/sld/BusBar.tsx`

**Props**:
```typescript
interface BusBarProps {
  label?: string;
  width?: string; // Tailwind CSS width class
  className?: string;
}
```

**Visual Design**:
- Horizontal bar with gradient background (primary color)
- Pulsing glow animation effect
- Optional label above the bar
- Customizable width via Tailwind classes

**Styling**:
- Height: `h-2` (8px)
- Rounded: `rounded-full`
- Gradient: `bg-gradient-to-r from-primary/80 via-primary to-primary/80`
- Glow effect: `pulse-glow` animation with box-shadow

### 4. ConnectionLine Component

**Location**: `src/components/sld/ConnectionLine.tsx`

**Props**:
```typescript
interface ConnectionLineProps {
  direction?: "vertical" | "horizontal";
  length?: number; // in pixels
  hasFlow?: boolean;
  flowDirection?: "down" | "up" | "left" | "right";
  className?: string;
}
```

**Visual Design**:
- Vertical or horizontal line
- Animated flow indicator (small circle) that moves along the line
- Flow direction determines animation direction:
  - `down`: Circle animates downward
  - `up`: Circle animates upward
- Line color: Primary color with opacity
- Flow indicator: Primary color with glow effect

**Animation**:
- Flow indicator uses CSS animations (`animate-flow-down`, `animate-flow-up`)
- Animation duration: 2 seconds, linear, infinite
- Flow indicator is a small circle (8px) that moves along the line path

## Icon Mapping

Device types map to Lucide React icons:

- `grid`: `Zap` icon
- `pv`: `Sun` icon (with `text-solar` color class)
- `wind`: `Wind` icon (with `text-wind` color class)
- `bess`: `Battery` icon (with `text-warning` color class)
- `generator`: `Power` icon
- `transformer`: `ArrowDownUp` icon
- `load`: `Home` icon

## Styling Requirements

### CSS Classes (Tailwind)

**SLD Node Variants**:
- `.sld-node-grid`: Border with primary color, light primary background
- `.sld-node-solar`: Border with yellow-400, light yellow background
- `.sld-node-wind`: Border with cyan-400, light cyan background
- `.sld-node-battery`: Border with warning color, light warning background
- `.sld-node`: Base card styling with border, padding, shadow

**Status Badges**:
- `.status-online`: Green background with green text and border
- `.status-warning`: Yellow background with yellow text and border
- `.status-offline`: Red background with red text and border

**Animations** (defined in `src/index.css`):
- `.pulse-glow`: Pulsing glow effect for bus bars
- `.animate-flow-down`: Flow indicator moving down
- `.animate-flow-up`: Flow indicator moving up

**Custom Colors**:
- `.text-solar`: Yellow color (#fde047)
- `.text-wind`: Cyan color (#22d3ee)
- `.text-load-commercial`: Purple color (#8b5cf6)

### Tailwind Config

Add these animations to `tailwind.config.ts`:

```typescript
keyframes: {
  'flow-down': {
    '0%': { transform: 'translateY(-100%)', opacity: '0' },
    '10%': { opacity: '1' },
    '90%': { opacity: '1' },
    '100%': { transform: 'translateY(100%)', opacity: '0' }
  },
  'flow-up': {
    '0%': { transform: 'translateY(100%)', opacity: '0' },
    '10%': { opacity: '1' },
    '90%': { opacity: '1' },
    '100%': { transform: 'translateY(-100%)', opacity: '0' }
  }
},
animation: {
  'flow-down': 'flow-down 2s linear infinite',
  'flow-up': 'flow-up 2s linear infinite'
}
```

## Data Loading

The SLD component loads data from a JSON file:

**File**: `src/mock-data/sld.json`

**Usage in SLD Page** (`src/pages/SLD.tsx`):
```typescript
import sldJsonData from "@/mock-data/sld.json";
import type { SLDData } from "@/components/sld/types";

const [sldData] = useState<SLDData>(sldJsonData as SLDData);
```

**JSON Import Support** (`src/vite-env.d.ts`):
```typescript
declare module "*.json" {
  const value: any;
  export default value;
}
```

## Special Features

### BESS (Battery) Display

When a device has `type: "bess"` and `properties.soc` is defined:
- Display a progress bar showing State of Charge (SOC) percentage
- Progress bar uses warning color
- Show text: "SOC: {soc}% | {capacity}"

### Power Flow Display

When a device has `powerFlow`:
- Display direction and value: "{direction}: {valueKW} kW"
- Examples: "import: 150 kW", "generate: 75 kW", "charge: 50 kW"

### Load Priority Styling

When a load device has `properties.priority`:
- `"HIGH"`: Red border (`border-destructive`)
- `"MEDIUM"`: Purple border (`border-load-commercial`)
- `"LOW"`: Default border

## Connection Rendering Rules

### Critical Requirements

1. **No Duplicate Lines**: Each connection must render exactly once
2. **Single Line Between Elements**: Only one line between Utility Grid and Main Transformer, only one line between Main Transformer and Main Bus
3. **Explicit Connections**: All connections must be defined in the `connections` array
4. **Bus Connections**: Connections to/from buses are rendered at the bus level, not at device level

### Connection Flow Direction

Flow direction is determined in this order:
1. Use `connection.flowDirection` if explicitly provided
2. Calculate from device levels: if `toLevel > fromLevel` → "down", if `toLevel < fromLevel` → "up"
3. Default to "down"

## Summary Panel

The summary panel displays key metrics at the bottom of the SLD:
- Grid Import/Export
- Total Generation
- Total Load
- Battery Status (Charging/Discharging)

Each summary card shows:
- Label (uppercase, monospace, muted)
- Value (large, bold, monospace, colored)
- Subtext (small, muted)

## Implementation Checklist

When implementing this SLD system, ensure:

- [ ] TypeScript types are defined in `src/components/sld/types.ts`
- [ ] All components are created in `src/components/sld/` directory
- [ ] CSS animations are added to `src/index.css` and `tailwind.config.ts`
- [ ] JSON data structure matches `SLDData` interface
- [ ] Connections array includes all required connections
- [ ] Bus is positioned between transformer and DERs (level 2)
- [ ] Each connection renders only once
- [ ] Flow animations work correctly (down/up directions)
- [ ] Device icons map correctly to device types
- [ ] Status badges display correct colors
- [ ] BESS shows SOC progress bar when `properties.soc` exists
- [ ] Load priority styling applies correctly
- [ ] Summary panel calculates and displays metrics

## Example Usage

```tsx
import { MicrogridSLD } from "@/components/sld/MicrogridSLD";
import sldJsonData from "@/mock-data/sld.json";
import type { SLDData } from "@/components/sld/types";

const SLD = () => {
  const [sldData] = useState<SLDData>(sldJsonData as SLDData);

  return (
    <div className="overflow-auto">
      <MicrogridSLD data={sldData} />
    </div>
  );
};
```

## Notes

- The component is fully data-driven - all visual elements are generated from the JSON data
- The layout is responsive and uses Tailwind CSS for styling
- All animations use CSS (no JavaScript-based animations)
- The component supports both light and dark themes via CSS variables
- Connection rendering is optimized to prevent duplicate lines
- The system is designed to be easily extensible for additional device types

