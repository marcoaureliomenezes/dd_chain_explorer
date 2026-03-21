#!/usr/bin/env python3
"""Generate fast_ingestion_2.excalidraw diagram for the Ethereum streaming pipeline."""
import json
import random
import os

random.seed(42)

# --- Layout constants ---
PYTHON_X, PYTHON_Y, PYTHON_W, PYTHON_H = 300, 120, 420, 610
KAFKA_X, KAFKA_Y, KAFKA_W, KAFKA_H = 790, 120, 370, 590
SPARK_X, SPARK_Y, SPARK_W, SPARK_H = 1230, 120, 360, 290
REDIS_X, REDIS_Y, REDIS_W, REDIS_H = 300, 810, 420, 200
S3_X, S3_Y, S3_W, S3_H = 1230, 490, 260, 90
ETH_X, ETH_Y, ETH_W, ETH_H = 40, 350, 210, 140
SSM_X, SSM_Y, SSM_W, SSM_H = 330, 40, 280, 55
SCHEMA_X, SCHEMA_Y, SCHEMA_W, SCHEMA_H = 790, 810, 280, 55

JOB_W, JOB_H = 340, 50
TOPIC_W, TOPIC_H = 310, 40
DB_W, DB_H = 90, 40
SPARK_JOB_W, SPARK_JOB_H = 310, 50

# Starting Y for inner elements
JOB_START_Y = 260
TOPIC_START_Y = 260
JOB_SPACING = 80
TOPIC_SPACING = 60

# Colors
GREEN_BG = "#b2f2bb"
PINK_BG = "#ffc9c9"
YELLOW_BG = "#ffec99"
BLUE_BG = "#a5d8ff"
LAVENDER_BG = "#dbe4ff"
BLACK = "#1e1e1e"
RED = "#e03131"
GREEN_ARROW = "#2f9e44"
BLUE_ARROW = "#1971c2"
TRANSPARENT = "transparent"

# File IDs for library images
KAFKA_LOGO = "77c8250381312e715c9f1d9c617897a9b8c049af"
REDIS_LOGO = "acad47909db7a58356ad319ae4135216907bbbc5"
PYTHON_LOGO = "b95e9c59ef75120ffd8321ba89b3a7d4ecac70e3"
SPARK_LOGO = "b2b5ee3b3f3413b734297b19c5a6d578ae18000d"

TIMESTAMP = 1724000000000

# --- Global state ---
elements = []
bound_elements_map = {}  # element_id -> list of {id, type}
index_counter = [0]

def next_index():
    """Generate sequential index strings: a0, a1, ..., aZ, b0, ..."""
    i = index_counter[0]
    index_counter[0] += 1
    letter = chr(ord('a') + i // 36)
    num = i % 36
    if num < 10:
        suffix = str(num)
    else:
        suffix = chr(ord('A') + num - 10)
    return f"{letter}{suffix}"

def seed():
    return random.randint(1, 2_000_000_000)

def register_bound(element_id, bound_id, bound_type):
    """Register a bound element relationship."""
    if element_id not in bound_elements_map:
        bound_elements_map[element_id] = []
    bound_elements_map[element_id].append({"id": bound_id, "type": bound_type})

def make_rect(id, x, y, w, h, bg, stroke=BLACK, group_ids=None, stroke_width=4):
    return {
        "id": id, "type": "rectangle",
        "x": x, "y": y, "width": w, "height": h,
        "strokeColor": stroke, "backgroundColor": bg,
        "fillStyle": "solid", "strokeWidth": stroke_width,
        "strokeStyle": "solid", "roughness": 0, "opacity": 100,
        "angle": 0, "groupIds": group_ids or [],
        "frameId": None, "index": next_index(),
        "roundness": None, "seed": seed(),
        "version": 1, "versionNonce": seed(),
        "isDeleted": False,
        "boundElements": [],  # filled later
        "updated": TIMESTAMP, "link": None, "locked": False
    }

def make_text(id, x, y, w, h, text, font_size=16, container_id=None,
              text_align="center", vertical_align="middle", group_ids=None,
              stroke_color=BLACK):
    return {
        "id": id, "type": "text",
        "x": x, "y": y, "width": w, "height": h,
        "text": text, "fontSize": font_size, "fontFamily": 5,
        "textAlign": text_align, "verticalAlign": vertical_align,
        "containerId": container_id,
        "originalText": text, "autoResize": True, "lineHeight": 1.25,
        "strokeColor": stroke_color, "backgroundColor": TRANSPARENT,
        "fillStyle": "solid", "strokeWidth": 4,
        "strokeStyle": "solid", "roughness": 0, "opacity": 100,
        "angle": 0, "groupIds": group_ids or [],
        "frameId": None, "index": next_index(),
        "roundness": None, "seed": seed(),
        "version": 1, "versionNonce": seed(),
        "isDeleted": False,
        "boundElements": None,
        "updated": TIMESTAMP, "link": None, "locked": False
    }

def make_image(id, x, y, w, h, file_id, group_ids=None):
    return {
        "id": id, "type": "image",
        "x": x, "y": y, "width": w, "height": h,
        "strokeColor": TRANSPARENT, "backgroundColor": TRANSPARENT,
        "fillStyle": "solid", "strokeWidth": 4,
        "strokeStyle": "solid", "roughness": 0, "opacity": 100,
        "angle": 0, "groupIds": group_ids or [],
        "frameId": None, "index": next_index(),
        "roundness": None, "seed": seed(),
        "version": 1, "versionNonce": seed(),
        "isDeleted": False,
        "boundElements": [],
        "updated": TIMESTAMP, "link": None, "locked": False,
        "status": "saved", "fileId": file_id,
        "scale": [1, 1], "crop": None
    }

def make_arrow(id, x, y, dx, dy, color, start_id=None, end_id=None,
               start_focus=0, end_focus=0, start_gap=1, end_gap=1):
    arrow = {
        "id": id, "type": "arrow",
        "x": x, "y": y,
        "width": abs(dx), "height": abs(dy),
        "strokeColor": color, "backgroundColor": TRANSPARENT,
        "fillStyle": "solid", "strokeWidth": 4,
        "strokeStyle": "solid", "roughness": 0, "opacity": 100,
        "angle": 0, "groupIds": [],
        "frameId": None, "index": next_index(),
        "roundness": {"type": 2}, "seed": seed(),
        "version": 1, "versionNonce": seed(),
        "isDeleted": False,
        "boundElements": [],
        "updated": TIMESTAMP, "link": None, "locked": False,
        "startBinding": None,
        "endBinding": None,
        "lastCommittedPoint": None,
        "startArrowhead": None,
        "endArrowhead": "arrow",
        "points": [[0, 0], [dx, dy]],
        "elbowed": False
    }
    if start_id:
        arrow["startBinding"] = {
            "elementId": start_id,
            "focus": start_focus,
            "gap": start_gap,
            "fixedPoint": None
        }
        register_bound(start_id, id, "arrow")
    if end_id:
        arrow["endBinding"] = {
            "elementId": end_id,
            "focus": end_focus,
            "gap": end_gap,
            "fixedPoint": None
        }
        register_bound(end_id, id, "arrow")
    return arrow

def add_box_with_text(box_id, text_id, x, y, w, h, bg, text, font_size=16,
                      group_ids=None, stroke=BLACK):
    """Add a rectangle with bound text inside it."""
    rect = make_rect(box_id, x, y, w, h, bg, stroke=stroke, group_ids=group_ids)
    register_bound(box_id, text_id, "text")
    
    # Approximate text dimensions
    text_h = font_size * 1.25
    text_w = len(text) * font_size * 0.55
    text_x = x + (w - text_w) / 2
    text_y = y + (h - text_h) / 2
    
    txt = make_text(text_id, text_x, text_y, text_w, text_h, text,
                    font_size=font_size, container_id=box_id,
                    group_ids=group_ids)
    
    elements.append(rect)
    elements.append(txt)
    return rect

# ============================================================
# BUILD THE DIAGRAM
# ============================================================

# --- Title ---
elements.append(make_text(
    "title", 50, 15, 700, 35,
    "Ethereum Streaming Data Capture Pipeline",
    font_size=28, text_align="left", vertical_align="top"
))

# --- Ethereum Network ---
eth_rect = make_rect("eth-box", ETH_X, ETH_Y, ETH_W, ETH_H, BLUE_BG, stroke=BLUE_ARROW)
register_bound("eth-box", "eth-text", "text")
elements.append(eth_rect)
elements.append(make_text(
    "eth-text", ETH_X + 20, ETH_Y + 40, 170, 50,
    "ETHEREUM\nNETWORK",
    font_size=20, container_id="eth-box"
))

# --- AWS SSM ---
add_box_with_text("ssm-box", "ssm-text", SSM_X, SSM_Y, SSM_W, SSM_H,
                  LAVENDER_BG, "AWS SSM (26 API Keys)", font_size=16,
                  stroke=BLUE_ARROW)

# --- Python Streaming Jobs Container ---
elements.append(make_rect("cont-python", PYTHON_X, PYTHON_Y, PYTHON_W, PYTHON_H,
                          GREEN_BG, group_ids=["grp-python"]))
elements.append(make_image("img-python", PYTHON_X + 10, PYTHON_Y + 10, 65, 65,
                           PYTHON_LOGO, group_ids=["grp-python"]))
elements.append(make_text(
    "title-python", PYTHON_X + 85, PYTHON_Y + 25, 300, 30,
    "Python Streaming Jobs", font_size=22,
    text_align="left", vertical_align="top", group_ids=["grp-python"]
))

# Job definitions: (id_suffix, label, y_offset)
jobs = [
    ("1", "mined_blocks_crawler (2x)", 0),
    ("2", "orphan_blocks_crawler (1x)", 1),
    ("3", "block_data_crawler (2x)", 2),
    ("4", "raw_txs_processor (6x)", 3),
    ("5", "tx_input_decoder (6x)", 4),
]

JOB_X = PYTHON_X + 40
job_positions = {}  # job_id -> (x, y, w, h)

for suffix, label, idx in jobs:
    y = JOB_START_Y + idx * JOB_SPACING
    box_id = f"job-{suffix}"
    text_id = f"job-{suffix}-text"
    add_box_with_text(box_id, text_id, JOB_X, y, JOB_W, JOB_H,
                      YELLOW_BG, label, group_ids=["grp-python"])
    job_positions[suffix] = (JOB_X, y, JOB_W, JOB_H)

# Add annotation text for logging
elements.append(make_text(
    "log-annotation", PYTHON_X + 30, PYTHON_Y + PYTHON_H - 90, 360, 40,
    "All jobs → mainnet.0 via KafkaLoggingHandler",
    font_size=14, text_align="center", vertical_align="top",
    group_ids=["grp-python"], stroke_color="#868e96"
))

# --- Kafka Cluster Container ---
elements.append(make_rect("cont-kafka", KAFKA_X, KAFKA_Y, KAFKA_W, KAFKA_H,
                          GREEN_BG, group_ids=["grp-kafka"]))
elements.append(make_image("img-kafka", KAFKA_X + 10, KAFKA_Y + 10, 65, 65,
                           KAFKA_LOGO, group_ids=["grp-kafka"]))
elements.append(make_text(
    "title-kafka", KAFKA_X + 85, KAFKA_Y + 25, 200, 30,
    "Kafka Cluster", font_size=22,
    text_align="left", vertical_align="top", group_ids=["grp-kafka"]
))

# Topic definitions: (number, label, y_offset)
topics = [
    ("0", "mainnet.0  (logs)", 0),
    ("1", "mainnet.1  (block metadata)", 1),
    ("2", "mainnet.2  (full blocks)", 2),
    ("3", "mainnet.3  (tx hashes · 8p)", 3),
    ("4", "mainnet.4  (full txs · 8p)", 4),
    ("5", "mainnet.5  (decoded input)", 5),
]

TOPIC_X = KAFKA_X + 30
topic_positions = {}

for num, label, idx in topics:
    y = TOPIC_START_Y + idx * TOPIC_SPACING
    box_id = f"topic-{num}"
    text_id = f"topic-{num}-text"
    add_box_with_text(box_id, text_id, TOPIC_X, y, TOPIC_W, TOPIC_H,
                      PINK_BG, label, font_size=14, group_ids=["grp-kafka"])
    topic_positions[num] = (TOPIC_X, y, TOPIC_W, TOPIC_H)

# --- Spark Streaming Container ---
elements.append(make_rect("cont-spark", SPARK_X, SPARK_Y, SPARK_W, SPARK_H,
                          GREEN_BG, group_ids=["grp-spark"]))
elements.append(make_image("img-spark", SPARK_X + 10, SPARK_Y + 10, 65, 65,
                           SPARK_LOGO, group_ids=["grp-spark"]))
elements.append(make_text(
    "title-spark", SPARK_X + 85, SPARK_Y + 25, 220, 30,
    "Spark Streaming", font_size=22,
    text_align="left", vertical_align="top", group_ids=["grp-spark"]
))

SPARK_JOB_X = SPARK_X + 25
spark_jobs = [
    ("1", "spark_api_key_monitor", 0),
    ("2", "spark_s3_multiplex", 1),
]
spark_positions = {}

for suffix, label, idx in spark_jobs:
    y = SPARK_Y + 120 + idx * 80
    box_id = f"spark-{suffix}"
    text_id = f"spark-{suffix}-text"
    add_box_with_text(box_id, text_id, SPARK_JOB_X, y, SPARK_JOB_W, SPARK_JOB_H,
                      YELLOW_BG, label, group_ids=["grp-spark"])
    spark_positions[suffix] = (SPARK_JOB_X, y, SPARK_JOB_W, SPARK_JOB_H)

# --- S3 Data Lake ---
add_box_with_text("s3-box", "s3-text", S3_X, S3_Y, S3_W, S3_H,
                  BLUE_BG, "S3 Data Lake (Parquet)", font_size=16,
                  stroke=BLUE_ARROW)

# --- Redis Cluster Container ---
elements.append(make_rect("cont-redis", REDIS_X, REDIS_Y, REDIS_W, REDIS_H,
                          GREEN_BG, group_ids=["grp-redis"]))
elements.append(make_image("img-redis", REDIS_X + 10, REDIS_Y + 10, 50, 50,
                           REDIS_LOGO, group_ids=["grp-redis"]))
elements.append(make_text(
    "title-redis", REDIS_X + 70, REDIS_Y + 18, 100, 25,
    "Redis", font_size=20,
    text_align="left", vertical_align="top", group_ids=["grp-redis"]
))

# Redis DB boxes
DB_START_X = REDIS_X + 15
DB_START_Y = REDIS_Y + 80
DB_SPACING_X = 100
DB_SPACING_Y = 50

redis_dbs = [
    ("0", "db0\nsemaphore", 0, 0),
    ("1", "db1\ncounters", 1, 0),
    ("2", "db2\nblock cache", 2, 0),
    ("3", "db3\nmonitoring", 3, 0),
    ("6", "db6\nABI cache", 0, 1),
]

db_positions = {}
for num, label, col, row in redis_dbs:
    x = DB_START_X + col * DB_SPACING_X
    y = DB_START_Y + row * DB_SPACING_Y
    box_id = f"redis-db{num}"
    text_id = f"rdb{num}-text"
    add_box_with_text(box_id, text_id, x, y, DB_W, DB_H,
                      PINK_BG, label, font_size=11,
                      group_ids=["grp-redis"])
    db_positions[num] = (x, y, DB_W, DB_H)

# --- Schema Registry ---
add_box_with_text("schema-reg", "schema-reg-text",
                  SCHEMA_X, SCHEMA_Y, SCHEMA_W, SCHEMA_H,
                  LAVENDER_BG, "Confluent Schema Registry", font_size=14,
                  stroke=BLUE_ARROW)

# ============================================================
# ARROWS
# ============================================================

def center(pos):
    """Get center of a (x, y, w, h) tuple."""
    return (pos[0] + pos[2] / 2, pos[1] + pos[3] / 2)

def right_center(pos):
    return (pos[0] + pos[2], pos[1] + pos[3] / 2)

def left_center(pos):
    return (pos[0], pos[1] + pos[3] / 2)

def bottom_center(pos):
    return (pos[0] + pos[2] / 2, pos[1] + pos[3])

def top_center(pos):
    return (pos[0] + pos[2] / 2, pos[1])

# Helper to create arrow between two positioned elements
def arrow_between(arrow_id, src_id, src_pos, dst_id, dst_pos, color,
                  src_side="right", dst_side="left"):
    """Create an arrow from src to dst."""
    if src_side == "right":
        sx, sy = right_center(src_pos)
    elif src_side == "bottom":
        sx, sy = bottom_center(src_pos)
    else:
        sx, sy = right_center(src_pos)
    
    if dst_side == "left":
        ex, ey = left_center(dst_pos)
    elif dst_side == "top":
        ex, ey = top_center(dst_pos)
    elif dst_side == "right":
        ex, ey = right_center(dst_pos)
    else:
        ex, ey = left_center(dst_pos)
    
    dx = ex - sx
    dy = ey - sy
    
    return make_arrow(arrow_id, sx, sy, dx, dy, color,
                      start_id=src_id, end_id=dst_id,
                      start_gap=1, end_gap=1)

# --- Data Flow Arrows (Red) ---

# Ethereum → Job 1
eth_pos = (ETH_X, ETH_Y, ETH_W, ETH_H)
elements.append(arrow_between(
    "arrow-eth-j1", "eth-box", eth_pos,
    "job-1", job_positions["1"], RED,
    src_side="right", dst_side="left"
))

# Job 1 → Topic 1
elements.append(arrow_between(
    "arrow-j1-t1", "job-1", job_positions["1"],
    "topic-1", topic_positions["1"], RED
))

# Topic 1 → Job 2 (consume)
elements.append(arrow_between(
    "arrow-t1-j2", "topic-1", topic_positions["1"],
    "job-2", job_positions["2"], RED,
    src_side="left", dst_side="right"  # arrow goes LEFT from topic to job
))

# Topic 1 → Job 3 (consume)
elements.append(arrow_between(
    "arrow-t1-j3", "topic-1", topic_positions["1"],
    "job-3", job_positions["3"], RED,
    src_side="left", dst_side="right"
))

# Job 3 → Topic 2
elements.append(arrow_between(
    "arrow-j3-t2", "job-3", job_positions["3"],
    "topic-2", topic_positions["2"], RED
))

# Job 3 → Topic 3
elements.append(arrow_between(
    "arrow-j3-t3", "job-3", job_positions["3"],
    "topic-3", topic_positions["3"], RED
))

# Topic 3 → Job 4 (consume)
elements.append(arrow_between(
    "arrow-t3-j4", "topic-3", topic_positions["3"],
    "job-4", job_positions["4"], RED,
    src_side="left", dst_side="right"
))

# Job 4 → Topic 4
elements.append(arrow_between(
    "arrow-j4-t4", "job-4", job_positions["4"],
    "topic-4", topic_positions["4"], RED
))

# Topic 4 → Job 5 (consume)
elements.append(arrow_between(
    "arrow-t4-j5", "topic-4", topic_positions["4"],
    "job-5", job_positions["5"], RED,
    src_side="left", dst_side="right"
))

# Job 5 → Topic 5
elements.append(arrow_between(
    "arrow-j5-t5", "job-5", job_positions["5"],
    "topic-5", topic_positions["5"], RED
))

# Python container → Topic 0 (all logs)
python_cont_pos = (PYTHON_X, PYTHON_Y, PYTHON_W, PYTHON_H)
elements.append(arrow_between(
    "arrow-logs-t0", "cont-python", python_cont_pos,
    "topic-0", topic_positions["0"], "#868e96"  # gray for logs
))

# --- Spark Flow Arrows (Green) ---

# Topic 0 → Spark API Key Monitor
elements.append(arrow_between(
    "arrow-t0-spark1", "topic-0", topic_positions["0"],
    "spark-1", spark_positions["1"], GREEN_ARROW
))

# Kafka container → Spark S3 Multiplex
kafka_cont_pos = (KAFKA_X, KAFKA_Y, KAFKA_W, KAFKA_H)
elements.append(arrow_between(
    "arrow-kafka-spark2", "cont-kafka", kafka_cont_pos,
    "spark-2", spark_positions["2"], GREEN_ARROW
))

# Spark S3 → S3
s3_pos = (S3_X, S3_Y, S3_W, S3_H)
elements.append(arrow_between(
    "arrow-spark2-s3", "spark-2", spark_positions["2"],
    "s3-box", s3_pos, GREEN_ARROW,
    src_side="bottom", dst_side="top"
))

# --- Redis Arrows (Blue) ---

# Job 2 → Redis db2 (block cache)
elements.append(arrow_between(
    "arrow-j2-rdb2", "job-2", job_positions["2"],
    "redis-db2", db_positions["2"], BLUE_ARROW,
    src_side="bottom", dst_side="top"
))

# Job 4 → Redis db0 (semaphore)
elements.append(arrow_between(
    "arrow-j4-rdb0", "job-4", job_positions["4"],
    "redis-db0", db_positions["0"], BLUE_ARROW,
    src_side="bottom", dst_side="top"
))

# Job 4 → Redis db1 (counters)
elements.append(arrow_between(
    "arrow-j4-rdb1", "job-4", job_positions["4"],
    "redis-db1", db_positions["1"], BLUE_ARROW,
    src_side="bottom", dst_side="top"
))

# Job 5 → Redis db6 (ABI cache)
elements.append(arrow_between(
    "arrow-j5-rdb6", "job-5", job_positions["5"],
    "redis-db6", db_positions["6"], BLUE_ARROW,
    src_side="bottom", dst_side="top"
))

# Spark API Key Monitor → Redis db1
elements.append(arrow_between(
    "arrow-spark1-rdb1", "spark-1", spark_positions["1"],
    "redis-db1", db_positions["1"], BLUE_ARROW,
    src_side="bottom", dst_side="right"  # long arrow going left and down
))

# AWS SSM → Python container
ssm_pos = (SSM_X, SSM_Y, SSM_W, SSM_H)
elements.append(arrow_between(
    "arrow-ssm-python", "ssm-box", ssm_pos,
    "cont-python", python_cont_pos, "#868e96",  # gray
    src_side="bottom", dst_side="top"
))

# ============================================================
# RESOLVE BOUND ELEMENTS
# ============================================================

for elem in elements:
    eid = elem.get("id")
    if eid and eid in bound_elements_map:
        elem["boundElements"] = bound_elements_map[eid]

# ============================================================
# FILES SECTION (reuse library images from fast_ingestion.excalidraw)
# ============================================================

# Read files from existing diagram
existing_path = os.path.join(os.path.dirname(__file__), "fast_ingestion.excalidraw")
with open(existing_path, 'r') as f:
    existing = json.load(f)

files = {}
needed_ids = {KAFKA_LOGO, REDIS_LOGO, PYTHON_LOGO, SPARK_LOGO}
for fid, fdata in existing.get("files", {}).items():
    if fid in needed_ids:
        files[fid] = fdata

# ============================================================
# ASSEMBLE FINAL DOCUMENT
# ============================================================

diagram = {
    "type": "excalidraw",
    "version": 2,
    "source": "https://excalidraw.com",
    "elements": elements,
    "appState": {
        "gridSize": 20,
        "gridStep": 5,
        "gridModeEnabled": False,
        "viewBackgroundColor": "#ffffff"
    },
    "files": files
}

output_path = os.path.join(os.path.dirname(__file__), "fast_ingestion_2.excalidraw")
with open(output_path, 'w') as f:
    json.dump(diagram, f, indent=2)

print(f"Generated {output_path}")
print(f"  Elements: {len(elements)}")
print(f"  Files: {len(files)}")
print(f"  Arrows: {sum(1 for e in elements if e.get('type') == 'arrow')}")
