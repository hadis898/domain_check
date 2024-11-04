# domain_check
[![Build Status](https://travis-ci.org/joemccann/dillinger.svg?branch=master)](https://travis-ci.org/joemccann/dillinger)
更新内容：

新增谷歌收录查询
更新进度显示，同时显示百度和谷歌的检查结果
修改结果统计，分别显示百度和谷歌的收录情况
在检查单个URL时增加延迟，避免请求过快
优化了结果展示，分别显示百度和谷歌的详细统计信息

#使用方法：

要用到的依赖包：
```sh
bashCopypip install requests pandas fake-useragent tqdm openpyxl
```
创建一个domains.txt文件，每行写入一个要查询的域名
运行脚本即可，结果会保存到Excel文件中

#注意事项：

谷歌搜索可能会更容易触发反爬机制，建议适当调整请求间隔时间
如果遇到频繁的验证码，可以考虑使用代理IP
结果文件会包含百度和谷歌的收录情况及详细统计信息

