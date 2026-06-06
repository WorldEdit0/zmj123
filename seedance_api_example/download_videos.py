import os
import pandas as pd
import requests
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

def parse_args():
    parser = argparse.ArgumentParser(description="多线程下载视频并记录成功列表")
    parser.add_argument("--csv_path", type=str, required=True, help="输入的 CSV 文件路径")
    parser.add_argument("--output_dir", type=str, required=True, help="视频保存的目标目录")
    parser.add_argument("--success_csv", type=str, default="download_success.csv", help="成功下载的记录文件")
    parser.add_argument("--shards_num", type=int, default=1, help="视频分片数")
    parser.add_argument("--shard_id", type=int, default=0, help="视频分片ID")
    parser.add_argument("--max_workers", type=int, default=6, help="线程池最大线程数")
    return parser.parse_args()

def download_video(row, output_dir):
    """
    单个视频下载函数
    返回: (是否成功, video_name, video_url)
    """
    video_name = row['video_name']
    url = row['video_url']
    status = row['status']

    if status != 'succeeded':
        return False, video_name, url

    save_path = os.path.join(output_dir, str(video_name))
    
    # 如果文件已存在且大小 > 0，视为成功
    if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
        return True, video_name, url

    try:
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(save_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return True, video_name, url
    except Exception as e:
        # 打印错误，方便调试
        # print(f"\n[Error] {video_name}: {e}")
        if os.path.exists(save_path):
            os.remove(save_path)
        return False, video_name, url

def main():
    args = parse_args()
    
    os.makedirs(args.output_dir, exist_ok=True)

    # 1. 读取并分片
    df = pd.read_csv(args.csv_path)
    # 过滤 status 为 succeeded 的任务
    df_to_process = df[df['status'] == 'succeeded'].copy()
    # 应用分片逻辑
    df_shard = df_to_process[df_to_process.index % args.shards_num == args.shard_id]
    
    tasks = df_shard.to_dict('records')
    total_tasks = len(tasks)
    print(f"分片 {args.shard_id}/{args.shards_num}: 准备处理 {total_tasks} 条记录")

    success_list = []

    # 2. 多线程执行
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        # 使用 submit 提交任务，以便后续获取结果
        future_to_video = {executor.submit(download_video, row, args.output_dir): row for row in tasks}
        
        with tqdm(total=total_tasks, desc=f"Shard {args.shard_id} Downloading") as pbar:
            for future in as_completed(future_to_video):
                is_success, v_name, v_url = future.result()
                if is_success:
                    success_list.append({"video_name": v_name, "video_url": v_url})
                pbar.update(1)

    # 3. 写入最终 CSV
    if success_list:
        success_df = pd.DataFrame(success_list)
        # 如果是分片运行，建议文件名区分开，防止冲突
        out_name = args.success_csv
        if args.shards_num > 1:
            name_part, ext = os.path.splitext(out_name)
            out_name = f"{name_part}_shard_{args.shard_id}{ext}"
            
        success_df.to_csv(out_name, index=False)
        print(f"\n下载完成！成功记录已保存至: {out_name} (共 {len(success_list)} 条)")
    else:
        print("\n没有成功下载任何视频。")

if __name__ == "__main__":
    main()