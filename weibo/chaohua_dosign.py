#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time : 15/7/2024 下午8:40
# @Author : G5116

import requests, time, threading, os, sys, random
from concurrent.futures import ThreadPoolExecutor, as_completed

# 获取当前文件的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录
project_root = os.path.dirname(current_dir)
# 将项目根目录添加到 sys.path
sys.path.append(project_root)
from utils import email_sender

# 新增全局锁和计数器
global_lock = threading.Lock()
completed_count = 0
success_count = 0


# 获取已关注超话列表信息（基于真实API机制）
def get_super_info_list():
    cookies = {
        'SUB': os.getenv('SUB_TOKEN'),
    }
    # 获取个人uid
    headers = {
        'referer': 'https://www.weibo.com/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0',
    }
    response = requests.get('https://www.weibo.com/ajax/feed/allGroups', cookies=cookies, headers=headers)
    uid = response.json()['groups'][0]['group'][0]['uid']
    # 获取超话列表
    all_super_info_list = []
    headers['referer'] = f'https://www.weibo.com/u/page/follow/{uid}/231093_-_chaohua'
    params = {
        'tabid': '231093_-_chaohua',
    }
    response = requests.get('https://www.weibo.com/ajax/profile/topicContent', params=params, cookies=cookies,
                            headers=headers)
    all_super_info_list = response.json()['data']['list']
    return all_super_info_list


# 读取固定参数文件
def load_params():
    params = {}
    file_path = os.path.join(current_dir, 'ch_fixed_params')
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            key, value = line.strip().split('=')
            params[key] = value
    return params


# 构建请求参数
def build_params(super_info):
    params = load_params()
    timestamp = int(time.time() * 1000)
    params['__rnd'] = str(timestamp)
    params['id'] = str(super_info['oid']).split(':')[1]
    print(params['id'])
    return params


# 开始签到
def start_sign(super_info, lock, results, retry_count=3):
    global success_count
    result = ''
    failure_reason = ''

    # 添加随机初始延迟
    time.sleep(random.uniform(0.3, 1.2))

    for attempt in range(retry_count):
        try:
            data = build_params(super_info)
            headers = {
                'user-agent': data['ua'],
            }

            response = requests.get(
                'https://weibo.com/p/aj/general/button',
                cookies=cookies,
                headers=headers,
                params=data,
                timeout=10
            )

            # 检查响应状态
            if response.status_code != 200:
                failure_reason = f'HTTP状态码{response.status_code}'
                if attempt < retry_count - 1:
                    time.sleep(random.uniform(2, 4))
                    continue
                else:
                    result = super_info['title'] + f'超话签到失败 (最后错误: {failure_reason})\n'
                    break

            response_data = response.json()

            # 修改状态判断逻辑
            if response_data['code'] in ('100000', 382004):
                result = super_info['title'] + '超话签到成功\n'
                with global_lock:
                    success_count += 1
                break
            else:
                failure_reason = f'错误码{response_data["code"]}'
                if attempt < retry_count - 1:
                    time.sleep(random.uniform(2, 4))
                    continue
                else:
                    result = super_info['title'] + f'超话签到失败 (最后错误: {failure_reason})\n'

        except requests.exceptions.Timeout:
            failure_reason = '请求超时'
            if attempt < retry_count - 1:
                time.sleep(random.uniform(3, 5))
                continue
            else:
                result = super_info['title'] + f'超话签到失败 (最后错误: {failure_reason})\n'

        except requests.exceptions.RequestException as e:
            failure_reason = f'网络错误: {str(e)}'
            if attempt < retry_count - 1:
                time.sleep(random.uniform(3, 5))
                continue
            else:
                result = super_info['title'] + f'超话签到失败 (最后错误: {failure_reason})\n'

        except Exception as e:
            failure_reason = f'未知错误: {str(e)}'
            if attempt < retry_count - 1:
                time.sleep(random.uniform(2, 4))
                continue
            else:
                result = super_info['title'] + f'超话签到失败 (最后错误: {failure_reason})\n'

    with global_lock:
        results.append(result)
        global completed_count
        completed_count += 1
    return result


def show_progress(total):
    while True:
        time.sleep(3)
        with global_lock:
            if completed_count >= total:
                break
            print(f"进度: {completed_count}/{total} ({completed_count / total * 100:.1f}%) - 成功: {success_count}")


def main():
    super_info_list = get_super_info_list()
    results = []
    lock = threading.Lock()
    start_time = time.time()
    max_workers = 6  # 降低并发数量，避免请求过于频繁

    print(f"开始超话签到，共{len(super_info_list)}个超话...")

    # 启动进度显示线程
    progress_thread = threading.Thread(target=show_progress, args=(len(super_info_list),), daemon=True)
    progress_thread.start()

    # 修改任务提交逻辑
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for super_info in super_info_list:
            future = executor.submit(
                start_sign,
                super_info=super_info,
                lock=lock,
                results=results
            )
            futures.append(future)

        for future in as_completed(futures):
            future.result()  # 触发异常会在此处抛出

    print("签到完成！")
    end_time = time.time()
    total_time = end_time - start_time

    # 统计签到结果
    success_rate = success_count / len(super_info_list) * 100 if super_info_list else 0
    summary = f"总共{len(super_info_list)}个超话，成功{success_count}个，成功率{success_rate:.1f}%，总耗时：{total_time:.2f}秒\n"

    print(f"\n{summary.strip()}")
    results.append(summary)

    # 发送邮件
    final_result = ''.join(results)
    email_sender.send_QQ_email_plain(final_result)


if __name__ == '__main__':
    cookies = {
        'SUB': os.getenv('SUB_TOKEN'),
    }
    main()
