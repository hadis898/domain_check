import requests
import time
import pandas as pd
from datetime import datetime
from fake_useragent import UserAgent
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from tqdm import tqdm

class DomainChecker:
    def __init__(self):
        self.ua = UserAgent()
        self.session = self._create_session()
        self.timeout = 10
        self.current_progress = None

    def _create_session(self):
        session = requests.Session()
        retry_strategy = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=20, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def get_headers(self):
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        }

    def clean_domain(self, url):
        url = url.lower().strip()
        url = re.sub(r'^https?://', '', url)
        url = re.sub(r'^www\.', '', url)
        return url.split('/')[0]

    def extract_number(self, text):
        if not text:
            return 0
        number = re.sub(r'[^0-9]', '', text)
        return int(number) if number else 0

    def update_progress_description(self, url, current, total, baidu_result=None, google_result=None):
        status = []
        if baidu_result:
            status.append(f"百度: {baidu_result}")
        if google_result:
            status.append(f"谷歌: {google_result}")
        status_str = " | ".join(status) if status else "检查中..."
        desc = f"进度: {current}/{total} - 当前: {url} - {status_str}"
        if self.current_progress:
            self.current_progress.set_description(desc)

    def check_baidu_index(self, url, max_retries=2):
        clean_url = self.clean_domain(url)
        encoded_url = quote(f"site:{clean_url}")
        search_url = f"https://www.baidu.com/s?wd={encoded_url}"

        for attempt in range(max_retries):
            try:
                response = self.session.get(search_url, headers=self.get_headers(), timeout=self.timeout)
                content = response.text

                if any(pattern in content for pattern in ["您的访问出现异常", "请输入验证码", "百度安全验证"]):
                    time.sleep(3)
                    continue

                result_patterns = [
                    r'找到相关结果数约([0-9,]+)个',
                    r'找到相关结果约([0-9,]+)个',
                    r'百度为您找到相关结果约([0-9,]+)个',
                    r'该网站共有([0-9,]+)个'
                ]
                for pattern in result_patterns:
                    match = re.search(pattern, content)
                    if match:
                        count = self.extract_number(match.group(1))
                        if count > 0:
                            return f'已收录({count:,})'

                if 'result c-container' in content and clean_url in content.lower():
                    return '已收录'

                if any(pattern in content for pattern in ["没有找到该URL对应的网页", "抱歉没有找到", "找不到与", "未找到相关结果"]):
                    return '未收录'

                return '未收录'
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                continue
        return '检查失败'

    def check_google_index(self, url, max_retries=2):
        clean_url = self.clean_domain(url)
        encoded_url = quote(f"site:{clean_url}")
        search_url = f"https://www.google.com/search?q={encoded_url}"

        for attempt in range(max_retries):
            try:
                response = self.session.get(search_url, headers=self.get_headers(), timeout=self.timeout)
                content = response.text

                if "detected unusual traffic" in content.lower():
                    time.sleep(3)
                    continue

                # 检查是否有结果数量
                result_pattern = r'约有 ([\d,]+) 条结果'
                match = re.search(result_pattern, content)
                if match:
                    count = self.extract_number(match.group(1))
                    if count > 0:
                        return f'已收录({count:,})'

                # 检查是否有搜索结果
                if 'id="search"' in content and clean_url in content.lower():
                    return '已收录'

                # 检查未收录情况
                if any(pattern in content.lower() for pattern in ["未找到与您的查询", "no results found", "did not match any documents"]):
                    return '未收录'

                return '未收录'
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                continue
        return '检查失败'

    def check_single_url(self, url, current, total):
        try:
            self.update_progress_description(url, current, total)
            baidu_result = self.check_baidu_index(url)
            time.sleep(1)  # 添加延迟避免请求过快
            google_result = self.check_google_index(url)
            self.update_progress_description(url, current, total, baidu_result, google_result)
            return {
                'URL': url,
                '检查时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                '百度收录': baidu_result,
                '谷歌收录': google_result
            }
        except Exception as e:
            print(f"\n检查 {url} 时出错: {str(e)}")
            return {
                'URL': url,
                '检查时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                '百度收录': '检查失败',
                '谷歌收录': '检查失败'
            }

    def batch_check(self, urls, num_threads=3):
        results = []
        total = len(urls)
        processed = 0
        
        with tqdm(total=total, desc="总体进度", unit="域名") as pbar:
            self.current_progress = pbar
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = []
                for url in urls:
                    processed += 1
                    future = executor.submit(self.check_single_url, url, processed, total)
                    futures.append(future)
                    time.sleep(0.5)  # 请求间隔

                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                        pbar.update(1)
                    except Exception as e:
                        print(f"\n处理结果时出错: {str(e)}")

            self.current_progress = None

            url_to_index = {url: index for index, url in enumerate(urls)}
            sorted_results = sorted(results, key=lambda x: url_to_index[x['URL']])
            return pd.DataFrame(sorted_results)

def read_urls_from_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"读取文件时出错: {str(e)}")
        return []

def main():
    try:
        import tqdm
    except ImportError:
        print("正在安装必要的包...")
        os.system('pip install tqdm')

    input_file = 'domains.txt'
    output_file = f'domain_index_check_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'

    if not os.path.exists(input_file):
        print(f"错误: 找不到输入文件 '{input_file}'")
        print("请创建一个domains.txt文件，每行写入一个要查询的域名")
        return

    urls_to_check = read_urls_from_file(input_file)

    if not urls_to_check:
        print("没有找到要检查的域名，请确保文件不为空且格式正确")
        return

    total_domains = len(urls_to_check)
    print(f"已读取 {total_domains} 个域名")
    print("开始检查...")
    print("=" * 50)

    start_time = time.time()
    checker = DomainChecker()
    results_df = checker.batch_check(urls_to_check)

    end_time = time.time()
    
    print("=" * 50)
    print("\n检查完成!")
    
    results_df.to_excel(output_file, index=False)

    # 计算百度和谷歌的成功率
    baidu_success = len(results_df[results_df['百度收录'].str.contains('已收录', na=False)])
    google_success = len(results_df[results_df['谷歌收录'].str.contains('已收录', na=False)])
    total_count = len(results_df)
    
    baidu_rate = (baidu_success / total_count) * 100 if total_count > 0 else 0
    google_rate = (google_success / total_count) * 100 if total_count > 0 else 0
    
    print(f"\n检查统计:")
    print(f"总域名数: {total_count}")
    print("\n百度收录情况:")
    print(f"已收录数: {baidu_success}")
    print(f"收录率: {baidu_rate:.1f}%")
    print("\n谷歌收录情况:")
    print(f"已收录数: {google_success}")
    print(f"收录率: {google_rate:.1f}%")
    print(f"\n总耗时: {end_time - start_time:.1f} 秒")
    print(f"平均每个域名耗时: {(end_time - start_time) / total_count:.1f} 秒")
    
    print(f"\n结果已保存到: {output_file}")

    # 统计详细收录情况
    print("\n详细收录统计:")
    print("\n百度收录状态:")
    baidu_statuses = results_df['百度收录'].value_counts()
    for status, count in baidu_statuses.items():
        print(f" {status}: {count}个")
        
    print("\n谷歌收录状态:")
    google_statuses = results_df['谷歌收录'].value_counts()
    for status, count in google_statuses.items():
        print(f" {status}: {count}个")

if __name__ == "__main__":
    main()