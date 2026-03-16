# Excalidraw Diagram Guide for AI

This document serves as a comprehensive reference for AI assistants to create and edit `.excalidraw` files programmatically. It covers the JSON format specification, element types, styling conventions, and project-specific patterns derived from analyzing the existing `fast_ingestion.excalidraw` diagram.

## Table of Contents

1. [File Format Overview](#file-format-overview)
2. [Top-Level Structure](#top-level-structure)
3. [Element Types](#element-types)
4. [Common Element Properties](#common-element-properties)
5. [Rectangle Elements](#rectangle-elements)
6. [Text Elements](#text-elements)
7. [Arrow Elements](#arrow-elements)
8. [Line Elements](#line-elements)
9. [Image Elements](#image-elements)
10. [Grouping](#grouping)
11. [Arrow Bindings](#arrow-bindings)
12. [Files Section (Library Images)](#files-section-library-images)
13. [appState Section](#appstate-section)
14. [Project Style Conventions](#project-style-conventions)
15. [Layout Patterns](#layout-patterns)
16. [Creating a New Diagram Step-by-Step](#creating-a-new-diagram-step-by-step)

---

## File Format Overview

Excalidraw files are JSON with the `.excalidraw` extension. They can be opened directly in [excalidraw.com](https://excalidraw.com) or the VS Code Excalidraw extension.

**Key characteristics:**
- Version 2 format
- All coordinates use a 2D canvas system (x increases rightward, y increases downward)
- Elements are rendered in order (later elements appear on top)
- IDs are nanoid-style strings (21 chars, alphanumeric + `-_`)
- Dimensions are in pixels

---

## Top-Level Structure

```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://excalidraw.com",
  "elements": [ ... ],
  "appState": { ... },
  "files": { ... }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `"excalidraw"` |
| `version` | number | Always `2` |
| `source` | string | Origin URL, typically `"https://excalidraw.com"` |
| `elements` | array | All diagram elements (shapes, text, arrows, images) |
| `appState` | object | Canvas configuration (grid, background) |
| `files` | object | Embedded images/files keyed by SHA hash |

---

## Element Types

| Type | Description |
|------|-------------|
| `rectangle` | Boxes, containers, cards |
| `text` | Labels, titles, descriptions |
| `arrow` | Directional connectors between elements |
| `line` | Non-directional lines (decorative, structural) |
| `image` | Embedded images (logos, icons) from the `files` section |

---

## Common Element Properties

Every element shares these base properties:

```json
{
  "type": "rectangle",
  "version": 100,
  "versionNonce": 123456789,
  "index": "a0",
  "isDeleted": false,
  "id": "unique-nanoid-string",
  "fillStyle": "solid",
  "strokeWidth": 4,
  "strokeStyle": "solid",
  "roughness": 0,
  "opacity": 100,
  "angle": 0,
  "x": 100,
  "y": 200,
  "strokeColor": "#1e1e1e",
  "backgroundColor": "#b2f2bb",
  "width": 300,
  "height": 150,
  "seed": 987654321,
  "groupIds": [],
  "frameId": null,
  "roundness": null,
  "boundElements": [],
  "updated": 1723764678927,
  "link": null,
  "locked": false
}
```

### Property Details

| Property | Type | Description |
|----------|------|-------------|
| `id` | string | Unique identifier. Use nanoid format: 21 chars from `A-Za-z0-9_-` |
| `type` | string | Element type: `rectangle`, `text`, `arrow`, `line`, `image` |
| `x`, `y` | number | Top-left position on canvas |
| `width`, `height` | number | Dimensions in pixels |
| `angle` | number | Rotation in radians (0 = no rotation) |
| `strokeColor` | string | Border/stroke color (hex) |
| `backgroundColor` | string | Fill color (hex). Use `"transparent"` for no fill |
| `fillStyle` | string | `"solid"`, `"hachure"`, `"cross-hatch"` |
| `strokeWidth` | number | Border thickness: `1`, `2`, or `4` |
| `strokeStyle` | string | `"solid"`, `"dashed"`, `"dotted"` |
| `roughness` | number | `0` = clean, `1` = slightly rough, `2` = very rough |
| `opacity` | number | 0-100 |
| `seed` | number | Random seed for consistent rendering. Use any large random integer |
| `version` | number | Increment counter. Start at `1` for new elements |
| `versionNonce` | number | Random integer for version tracking |
| `index` | string | Z-order index. Use base-62 strings: `"a0"`, `"a1"`, ..., `"aZ"`, `"b0"`, etc. |
| `isDeleted` | boolean | Soft-delete flag. Always `false` for visible elements |
| `groupIds` | array | List of group IDs this element belongs to |
| `frameId` | null | Frame containment (usually `null`) |
| `roundness` | object/null | `null` for sharp corners, `{"type": 3}` for rounded rectangles, `{"type": 2}` for rounded arrows |
| `boundElements` | array | Elements bound to this element (arrows, contained text) |
| `updated` | number | Unix timestamp in milliseconds |
| `link` | string/null | URL link (usually `null`) |
| `locked` | boolean | Whether element is locked from editing |

---

## Rectangle Elements

Rectangles are the primary building blocks for containers, cards, and boxes.

```json
{
  "id": "rect-001",
  "type": "rectangle",
  "x": 100,
  "y": 200,
  "width": 383,
  "height": 603,
  "strokeColor": "#1e1e1e",
  "backgroundColor": "#b2f2bb",
  "fillStyle": "solid",
  "strokeWidth": 4,
  "strokeStyle": "solid",
  "roughness": 0,
  "opacity": 100,
  "angle": 0,
  "groupIds": ["group-1"],
  "roundness": null,
  "boundElements": [
    { "id": "arrow-001", "type": "arrow" },
    { "id": "text-001", "type": "text" }
  ],
  "seed": 123456789,
  "version": 1,
  "versionNonce": 987654321,
  "index": "a0",
  "isDeleted": false,
  "frameId": null,
  "updated": 1723764678927,
  "link": null,
  "locked": false
}
```

### Rectangle as Container (with bound text)

When a rectangle contains text, both elements reference each other:

**Rectangle** has `boundElements` entry:
```json
"boundElements": [
  { "id": "text-inside", "type": "text" }
]
```

**Text** has `containerId`:
```json
"containerId": "rect-container",
"verticalAlign": "middle",
"textAlign": "center"
```

---

## Text Elements

Text can be standalone or bound inside a container element.

### Standalone Text
```json
{
  "id": "text-001",
  "type": "text",
  "x": 150,
  "y": 250,
  "width": 200,
  "height": 25,
  "text": "My Label",
  "fontSize": 20,
  "fontFamily": 5,
  "textAlign": "left",
  "verticalAlign": "top",
  "containerId": null,
  "originalText": "My Label",
  "autoResize": true,
  "lineHeight": 1.25,
  "strokeColor": "#1e1e1e",
  "backgroundColor": "transparent",
  "fillStyle": "solid",
  "strokeWidth": 4,
  "strokeStyle": "solid",
  "roughness": 0,
  "opacity": 100,
  "angle": 0,
  "groupIds": ["group-1"],
  "roundness": null,
  "boundElements": null,
  "seed": 111222333,
  "version": 1,
  "versionNonce": 444555666,
  "index": "a1",
  "isDeleted": false,
  "frameId": null,
  "updated": 1723764678927,
  "link": null,
  "locked": false
}
```

### Text Properties

| Property | Type | Description |
|----------|------|-------------|
| `text` | string | Displayed text. Use `\n` for line breaks |
| `fontSize` | number | Font size in pixels. Common: `16`, `20`, `28`, `36` |
| `fontFamily` | number | `1` = Virgil (hand-drawn), `2` = Helvetica, `3` = Cascadia, `5` = Excalifont |
| `textAlign` | string | `"left"`, `"center"`, `"right"` |
| `verticalAlign` | string | `"top"`, `"middle"`. Use `"middle"` for bound text |
| `containerId` | string/null | ID of parent container. `null` for standalone text |
| `originalText` | string | Same as `text` (used for undo tracking) |
| `autoResize` | boolean | Whether text auto-resizes its container |
| `lineHeight` | number | Line height multiplier. Typically `1.25` |

### Bound Text (inside a rectangle)
```json
{
  "id": "text-inside",
  "type": "text",
  "x": 110,
  "y": 215,
  "width": 180,
  "height": 20,
  "text": "Topic Name",
  "fontSize": 16,
  "fontFamily": 5,
  "textAlign": "center",
  "verticalAlign": "middle",
  "containerId": "rect-container",
  "originalText": "Topic Name",
  "autoResize": true,
  "lineHeight": 1.25,
  "boundElements": null
}
```

> **Important:** When text is bound to a container, the text's `x`/`y` are auto-calculated by Excalidraw. Set them approximately centered within the container. The `width`/`height` should match the text's rendered size.

---

## Arrow Elements

Arrows connect elements and show data flow direction.

```json
{
  "id": "arrow-001",
  "type": "arrow",
  "x": 500,
  "y": 300,
  "width": 200,
  "height": 5,
  "strokeColor": "#e03131",
  "backgroundColor": "#b2f2bb",
  "fillStyle": "solid",
  "strokeWidth": 4,
  "strokeStyle": "solid",
  "roughness": 0,
  "opacity": 100,
  "angle": 0,
  "groupIds": [],
  "roundness": { "type": 2 },
  "boundElements": [],
  "seed": 777888999,
  "version": 1,
  "versionNonce": 111222333,
  "index": "a5",
  "isDeleted": false,
  "frameId": null,
  "updated": 1723764678927,
  "link": null,
  "locked": false,
  "startBinding": {
    "elementId": "source-element-id",
    "focus": 0.0,
    "gap": 5,
    "fixedPoint": null
  },
  "endBinding": {
    "elementId": "target-element-id",
    "focus": 0.0,
    "gap": 1,
    "fixedPoint": null
  },
  "lastCommittedPoint": null,
  "startArrowhead": null,
  "endArrowhead": "arrow",
  "points": [
    [0, 0],
    [200, 5]
  ],
  "elbowed": false
}
```

### Arrow-Specific Properties

| Property | Type | Description |
|----------|------|-------------|
| `startBinding` | object/null | Connection to source element |
| `endBinding` | object/null | Connection to target element |
| `startArrowhead` | string/null | `null` (no head) or `"arrow"` |
| `endArrowhead` | string/null | `"arrow"` for standard arrowhead |
| `points` | array | Array of `[x, y]` offsets from the arrow's origin. First point is always `[0, 0]` |
| `elbowed` | boolean | `false` for curved/straight, `true` for right-angle elbowed |

### Points Array

The `points` array defines the arrow's path as offsets from `(x, y)`:
- First point: always `[0, 0]` (start)
- Last point: `[dx, dy]` where dx/dy are offsets from start
- Intermediate points create bends

The arrow's `width` and `height` should match the bounding box of all points.

---

## Line Elements

Lines are non-directional connectors or decorative strokes.

```json
{
  "id": "line-001",
  "type": "line",
  "x": 300,
  "y": 400,
  "width": 133,
  "height": 1,
  "strokeColor": "#1971c2",
  "fillStyle": "solid",
  "strokeWidth": 4,
  "strokeStyle": "solid",
  "roughness": 0,
  "opacity": 100,
  "groupIds": [],
  "roundness": null,
  "startBinding": null,
  "endBinding": null,
  "startArrowhead": null,
  "endArrowhead": null,
  "points": [
    [0, 0],
    [133, -1]
  ],
  "lastCommittedPoint": null
}
```

Lines can also be used as filled triangles/polygons by using 3+ points that form a closed shape (with `fillStyle: "solid"` and `backgroundColor: "#1e1e1e"`).

---

## Image Elements

Images reference files in the `files` section via `fileId`.

```json
{
  "id": "img-001",
  "type": "image",
  "x": 100,
  "y": 200,
  "width": 172,
  "height": 172,
  "strokeColor": "transparent",
  "backgroundColor": "transparent",
  "fillStyle": "solid",
  "strokeWidth": 4,
  "strokeStyle": "solid",
  "roughness": 0,
  "opacity": 100,
  "angle": 0,
  "groupIds": ["group-1"],
  "roundness": null,
  "boundElements": [],
  "seed": 555666777,
  "version": 1,
  "versionNonce": 888999000,
  "index": "a2",
  "isDeleted": false,
  "frameId": null,
  "updated": 1723764678927,
  "link": null,
  "locked": false,
  "status": "saved",
  "fileId": "77c8250381312e715c9f1d9c617897a9b8c049af",
  "scale": [1, 1],
  "crop": null
}
```

### Image-Specific Properties

| Property | Type | Description |
|----------|------|-------------|
| `fileId` | string | SHA hash referencing an entry in the `files` section |
| `status` | string | Always `"saved"` for persisted images |
| `scale` | array | `[scaleX, scaleY]`, typically `[1, 1]` |
| `crop` | null | Crop settings (usually `null`) |

---

## Grouping

Elements can be grouped by sharing the same `groupIds` entry. Groups can be nested.

```json
// Element A in group
"groupIds": ["kafka-group"]

// Element B in same group
"groupIds": ["kafka-group"]

// Element C in nested group
"groupIds": ["inner-group", "kafka-group"]
```

**Conventions:**
- Use descriptive group IDs for clarity
- A group makes elements move/select together
- Nested groups: inner group ID comes first in array

---

## Arrow Bindings

When an arrow connects to an element, both sides must be configured:

### Arrow side (startBinding / endBinding)
```json
"startBinding": {
  "elementId": "source-rect-id",
  "focus": 0.0,
  "gap": 5,
  "fixedPoint": null
}
```

| Property | Type | Description |
|----------|------|-------------|
| `elementId` | string | ID of the connected element |
| `focus` | number | Position along the element's edge. `-1` to `1`. `0` = center |
| `gap` | number | Distance from element's border. `1` = touching |
| `fixedPoint` | null | Fixed attachment point (usually `null`) |

### Target element side (boundElements)
The connected element must list the arrow in its `boundElements`:
```json
"boundElements": [
  { "id": "arrow-001", "type": "arrow" }
]
```

> **Critical:** Both sides must reference each other. If an arrow binds to element X, then element X must have that arrow in its `boundElements` array, and the arrow must reference X's ID in `startBinding` or `endBinding`.

---

## Files Section (Library Images)

The `files` section stores embedded images as base64 data URLs, keyed by their content hash.

```json
"files": {
  "77c8250381312e715c9f1d9c617897a9b8c049af": {
    "mimeType": "image/svg+xml",
    "id": "77c8250381312e715c9f1d9c617897a9b8c049af",
    "dataURL": "data:image/svg+xml;base64,PHN2Zy...",
    "created": 1723764678927,
    "lastRetrieved": 1723771953901
  }
}
```

### File Entry Properties

| Property | Type | Description |
|----------|------|-------------|
| `mimeType` | string | `"image/svg+xml"` or `"image/png"` |
| `id` | string | Same as the key (SHA hash of content) |
| `dataURL` | string | Base64-encoded data URL |
| `created` | number | Unix timestamp in ms |
| `lastRetrieved` | number | Unix timestamp in ms |

### Project Library Images

These are the shared logo images available for reuse:

| File ID | Type | Description |
|---------|------|-------------|
| `77c8250381312e715c9f1d9c617897a9b8c049af` | SVG | **Apache Kafka** logo |
| `acad47909db7a58356ad319ae4135216907bbbc5` | SVG | **Redis** logo |
| `6b1023d2ce1416f7cec51de16d42a4be4a447bf1` | SVG | **Confluent/Kafka Connect** logo |
| `b95e9c59ef75120ffd8321ba89b3a7d4ecac70e3` | SVG | **Python** logo |
| `b2b5ee3b3f3413b734297b19c5a6d578ae18000d` | PNG | **Apache Spark** logo |

To use a library image, create an `image` element with `"fileId"` pointing to one of these hashes, and include the corresponding entry in the `files` section.

---

## appState Section

```json
"appState": {
  "gridSize": 20,
  "gridStep": 5,
  "gridModeEnabled": false,
  "viewBackgroundColor": "#ffffff"
}
```

| Property | Type | Description |
|----------|------|-------------|
| `gridSize` | number | Grid cell size in pixels |
| `gridStep` | number | Grid subdivision |
| `gridModeEnabled` | boolean | Whether grid snapping is active |
| `viewBackgroundColor` | string | Canvas background color |

---

## Project Style Conventions

### Color Palette

| Color | Hex | Usage |
|-------|-----|-------|
| Green background | `#b2f2bb` | Service group containers (Kafka cluster, DynamoDB) |
| Pink background | `#ffc9c9` | Kafka topics, DynamoDB entities |
| Yellow background | `#ffec99` | Jobs, connectors, workers |
| Light blue background | `#a5d8ff` | External systems (Ethereum network) |
| Black stroke | `#1e1e1e` | Default stroke/text color |
| Red arrow | `#e03131` | Primary data flow (produce/consume) |
| Green arrow | `#2f9e44` | Secondary data flow |
| Blue arrow | `#1971c2` | Bidirectional flow, read/write connections |

### Typography

| Element | Font Size | Font Family |
|---------|-----------|-------------|
| Section titles | `28` - `36` | `5` (Excalifont) |
| Component labels | `20` | `5` |
| Detail text | `16` | `5` |
| Small annotations | `12` - `14` | `5` |

### Standard Dimensions

| Component | Width | Height | Notes |
|-----------|-------|--------|-------|
| Service container | 300-400 | 500-700 | Green background, groups inner elements |
| Kafka topic box | 200-280 | 35-40 | Pink background, bound text centered |
| DynamoDB entity box | 80-120 | 35-50 | Pink background, bound text centered |
| Job/worker box | 200-280 | 35-50 | Yellow background, bound text centered |
| Logo image | 100-172 | 100-172 | Aspect ratio preserved |

### Global Settings

- `roughness: 0` — Clean, non-hand-drawn style throughout
- `strokeWidth: 4` — Thick borders for visibility
- `fontFamily: 5` — Excalifont for all text
- `fillStyle: "solid"` — Solid fills everywhere
- `strokeStyle: "solid"` — No dashed/dotted lines (except decorative)

---

## Layout Patterns

### Service Group Pattern

A service (e.g., Kafka, DynamoDB) is represented as a large green rectangle containing:
1. A logo image (top area)
2. Multiple inner boxes (topics, databases) stacked vertically
3. All elements share a `groupId`

```
┌─────────────────────────┐  ← Green container (#b2f2bb)
│  [Kafka Logo]           │
│                         │
│  ┌───────────────────┐  │  ← Pink topic box (#ffc9c9)
│  │  mainnet.1        │  │
│  └───────────────────┘  │
│  ┌───────────────────┐  │
│  │  mainnet.2        │  │
│  └───────────────────┘  │
│  ... more topics ...    │
└─────────────────────────┘
```

### Job/Worker Pattern

Jobs are yellow boxes with descriptive labels:

```
┌───────────────────────────┐  ← Yellow box (#ffec99)
│  mined_blocks_crawler     │
│  replica 1                │
└───────────────────────────┘
```

### Data Flow Pattern

Arrows connect producers to topics and topics to consumers:

```
[Job] ──red arrow──→ [Topic] ──red arrow──→ [Job]
                         ↑
                     blue arrow
                         |
                     [DynamoDB]
```

---

## Creating a New Diagram Step-by-Step

### 1. Start with the skeleton

```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://excalidraw.com",
  "elements": [],
  "appState": {
    "gridSize": 20,
    "gridStep": 5,
    "gridModeEnabled": false,
    "viewBackgroundColor": "#ffffff"
  },
  "files": {}
}
```

### 2. Plan your layout

Sketch the layout on a grid. Typical arrangement:
- Left: Source systems
- Center: Processing (jobs/services)
- Right: Data stores (Kafka, DynamoDB, S3)

Use x-coordinates in multiples of 20 for alignment.

### 3. Create container elements first

Large green rectangles for service groups.

### 4. Add inner elements

Topics, databases, and jobs inside containers.

### 5. Add logos

Image elements referencing library file IDs.

### 6. Connect with arrows

Create arrows with proper bindings to source/target elements.

### 7. Add the files section

Include all referenced image files in the `files` object.

### 8. Validate

- Every `fileId` in an image element must exist in `files`
- Every arrow binding `elementId` must reference an existing element
- Every bound element must list the arrow in its `boundElements`
- Element `id` values must be unique
- Index values should be in sorted order

### ID Generation

For generating IDs programmatically, use this pattern:
- 21 characters from the set: `A-Za-z0-9_-`
- Example: `"xK9mR3pQ7wT2yJ5uI8vN6"`
- Or use simpler readable IDs for easier maintenance: `"kafka-container"`, `"topic-mainnet-1"`

> **Note:** Excalidraw accepts any string as an ID, but nanoid format is conventional.

---

## Quick Reference: Minimal Element Templates

### Minimal Rectangle
```json
{"id":"r1","type":"rectangle","x":0,"y":0,"width":200,"height":40,"strokeColor":"#1e1e1e","backgroundColor":"#ffc9c9","fillStyle":"solid","strokeWidth":4,"strokeStyle":"solid","roughness":0,"opacity":100,"angle":0,"groupIds":[],"frameId":null,"index":"a0","roundness":null,"seed":1,"version":1,"versionNonce":1,"isDeleted":false,"boundElements":[],"updated":1723764678927,"link":null,"locked":false}
```

### Minimal Text
```json
{"id":"t1","type":"text","x":10,"y":10,"width":180,"height":20,"text":"Label","fontSize":16,"fontFamily":5,"textAlign":"center","verticalAlign":"middle","containerId":"r1","originalText":"Label","autoResize":true,"lineHeight":1.25,"strokeColor":"#1e1e1e","backgroundColor":"transparent","fillStyle":"solid","strokeWidth":4,"strokeStyle":"solid","roughness":0,"opacity":100,"angle":0,"groupIds":[],"frameId":null,"index":"a1","roundness":null,"seed":2,"version":1,"versionNonce":2,"isDeleted":false,"boundElements":null,"updated":1723764678927,"link":null,"locked":false}
```

### Minimal Arrow
```json
{"id":"a1","type":"arrow","x":200,"y":20,"width":100,"height":0,"strokeColor":"#e03131","backgroundColor":"transparent","fillStyle":"solid","strokeWidth":4,"strokeStyle":"solid","roughness":0,"opacity":100,"angle":0,"groupIds":[],"frameId":null,"index":"a2","roundness":{"type":2},"seed":3,"version":1,"versionNonce":3,"isDeleted":false,"boundElements":[],"updated":1723764678927,"link":null,"locked":false,"startBinding":{"elementId":"r1","focus":0,"gap":1,"fixedPoint":null},"endBinding":{"elementId":"r2","focus":0,"gap":1,"fixedPoint":null},"lastCommittedPoint":null,"startArrowhead":null,"endArrowhead":"arrow","points":[[0,0],[100,0]],"elbowed":false}
```

### Minimal Image
```json
{"id":"i1","type":"image","x":50,"y":50,"width":100,"height":100,"strokeColor":"transparent","backgroundColor":"transparent","fillStyle":"solid","strokeWidth":4,"strokeStyle":"solid","roughness":0,"opacity":100,"angle":0,"groupIds":[],"frameId":null,"index":"a3","roundness":null,"seed":4,"version":1,"versionNonce":4,"isDeleted":false,"boundElements":[],"updated":1723764678927,"link":null,"locked":false,"status":"saved","fileId":"77c8250381312e715c9f1d9c617897a9b8c049af","scale":[1,1],"crop":null}
```
