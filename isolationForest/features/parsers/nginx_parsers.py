import re
from datetime import datetime


class NginxLogParser:
    """
    Nginx访问日志解析器
    
    功能：解析Nginx标准格式的访问日志，将日志行转换为结构化的字典
    """

    # Nginx访问日志的正则表达式模式
    # 匹配格式：IP - - [时间] "方法 URL 协议" 状态码 响应大小
    log_pattern = re.compile(
        r'(?P<ip>\S+) '                # 客户端IP地址
        r'\S+ \S+ '                    # 远程登录名和用户（忽略）
        r'\[(?P<time>.*?)\] '          # 时间戳
        r'"(?P<method>\S+) '           # HTTP请求方法（GET/POST等）
        r'(?P<url>\S+) '               # 请求的URL路径
        r'(?P<protocol>[^"]+)" '       # HTTP协议版本
        r'(?P<status>\d+) '            # HTTP状态码
        r'(?P<size>\d+)'               # 响应大小（字节）
    )

    def parse_line(self, line: str) -> dict | None:
        """
        解析单行Nginx日志
        
        参数:
            line: str - 单行Nginx日志字符串
        
        返回:
            dict | None - 解析成功返回包含日志信息的字典，解析失败返回None
        """
        # 使用正则表达式匹配日志行
        match = self.log_pattern.match(line)

        # 如果匹配失败，返回None
        if not match:
            return None

        # 获取匹配的所有组作为字典
        data = match.groupdict()

        # 类型转换：将状态码和响应大小转换为整数
        data["status"] = int(data["status"])
        data["size"] = int(data["size"])

        # 解析时间戳，转换为datetime对象
        data["time"] = self._parse_time(data["time"])

        return data

    def _parse_time(self, time_str: str) -> datetime | str:
        """
        将Nginx时间格式转换为datetime对象
        
        参数:
            time_str: str - Nginx格式的时间字符串（如：01/Jan/2024:12:34:56 +0000）
        
        返回:
            datetime | str - 成功返回datetime对象，失败返回原始时间字符串
        """
        try:
            # 解析Nginx时间格式：日/月/年:时:分:秒 时区
            return datetime.strptime(time_str, "%d/%b/%Y:%H:%M:%S %z")
        except Exception:
            # 如果解析失败，返回原始时间字符串
            return time_str


def parse_log_file(filepath: str) -> list:
    """
    解析整个Nginx日志文件
    
    参数:
        filepath: str - 日志文件路径
    
    返回:
        list - 包含所有解析成功的日志记录的列表，每个元素为一个日志字典
    """
    # 创建解析器实例
    parser = NginxLogParser()
    # 存储解析结果的列表
    logs = []

    # 打开日志文件并逐行解析
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            # 解析单行日志（去除首尾空白）
            result = parser.parse_line(line.strip())

            # 如果解析成功，添加到结果列表
            if result:
                logs.append(result)

    return logs


if __name__ == "__main__":
    text_list=parse_log_file("logs\\raw_data\\nginx\\腾讯云_nginx-all.log")
