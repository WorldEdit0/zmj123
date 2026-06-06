import os
import json
import csv
import time
import argparse
from tqdm import tqdm
from volcenginesdkarkruntime import Ark

# 参数解析
parser = argparse.ArgumentParser(description="Infer video with skip logic and real-time CSV saving")
parser.add_argument("--input_json", type=str, required=True, help="Path to input JSON file")
parser.add_argument("--csv_path", type=str, default="video_results.csv", help="Path to output CSV file")
parser.add_argument("--num_shards", type=int, required=True, help="Number of shards")
parser.add_argument("--shard_id", type=int, required=True, help="Shard ID")
parser.add_argument("--split_index", type=int, required=True)
parser.add_argument("--split_num", type=int, required=True)

# 初始化 Ark 客户端
client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=r'',
)

def main(args):
    # 1. 加载数据
    if not os.path.exists(args.input_json):
        print(f"Error: {args.input_json} not found.")
        return

    with open(args.input_json, "r") as f:
        json_data = json.load(f)
    
    items = json_data[args.shard_id::args.num_shards]
    items = items[args.split_index::args.split_num]
    
    # 2. 检测已存在的 video_name (断点续传逻辑)
    processed_names = set()
    file_exists = os.path.isfile(args.csv_path)
    
    if file_exists:
        with open(args.csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 只有状态为 succeeded 的才跳过，或者只要存在就跳过（根据需求调整）
                # 这里默认只要 CSV 里有这个名字就跳过
                if row.get('video_name'):
                    processed_names.add(row['video_name'])
        print(f"Found {len(processed_names)} existing records. These will be skipped.")

    fieldnames = ['video_name', 'video_url', 'status', 'duration_sec', 'fps', 'expected_shots', 'scene_id', 'category']

    # 3. 使用 'a' 模式追加
    with open(args.csv_path, mode='a', newline='', encoding='utf-8', buffering=1) as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
            csvfile.flush()
            os.fsync(csvfile.fileno())

        # 4. 循环处理
        for item in tqdm(items, desc=f"Shard {args.shard_id}"):
            video_name = f'{int(item["global_index"]):05d}.mp4'
            caption = item["caption"]

            # --- 跳过检测 ---
            if video_name in processed_names:
                continue 
            # ----------------

            try:
                # 创建任务 —— multi-shot 源视频生成
                # 注意：caption 已经在 JSON 里写好 [shot tag] 风格的多镜头指令，
                # 不要再包裹"相机机位固定/只有一个场景"这类反多镜头的提示。
                duration = int(item.get("duration_sec", 15))   # 多镜头默认 15s（Seedance 2.0 Pro 上限）
                ratio = item.get("ratio", "16:9")
                resolution = item.get("resolution", "1080p")    # benchmark 质量优先用 1080p

                create_result = client.content_generation.tasks.create(
                    model="doubao-seedance-2-0-260128",
                    content=[{
                        "type": "text",
                        "text": caption
                    }],
                    ratio=ratio,
                    duration=duration,
                    watermark=False,
                    resolution=resolution,
                    generate_audio=False,
                )
                task_id = create_result.id

                # 轮询任务状态
                final_url = ""
                final_status = ""
                while True:
                    get_result = client.content_generation.tasks.get(task_id=task_id)
                    final_status = get_result.status
                    
                    if final_status == "succeeded":
                        print("----- task succeeded -----")
                        print(get_result)
                        final_url = get_result.content.video_url
                        break
                    elif final_status == "failed":
                        print(f"\nTask failed for {video_name}: {get_result.error}")
                        break
                    else:
                        time.sleep(3)

                # 5. 实时写入并强制刷盘（含 multi-shot 元数据，供下游 TransNetV2 / 评测复用）
                writer.writerow({
                    'video_name': video_name,
                    'video_url': final_url if final_url else "FAILED",
                    'status': final_status,
                    'duration_sec': duration,
                    'fps': item.get("fps", 24),
                    'expected_shots': item.get("expected_shots", ""),
                    'scene_id': item.get("scene_id", ""),
                    'category': item.get("category", ""),
                })

                csvfile.flush()
                # os.fsync(csvfile.fileno())

            except Exception as e:
                print(f"\n[Exception] {video_name}: {e}")
                writer.writerow({
                    'video_name': video_name,
                    'video_url': "ERROR",
                    'status': "exception",
                    'duration_sec': item.get("duration_sec", ""),
                    'fps': item.get("fps", ""),
                    'expected_shots': item.get("expected_shots", ""),
                    'scene_id': item.get("scene_id", ""),
                    'category': item.get("category", ""),
                })
                csvfile.flush()
                os.fsync(csvfile.fileno())
                continue

if __name__ == "__main__":
    args = parser.parse_args()
    main(args)