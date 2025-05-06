<div align="center">

# 🌟 JM-Cosmos

[![版本](https://img.shields.io/badge/版本-v1.0.6-blue.svg)](https://github.com/GEMILUXVII/astrbot_plugin_jm_cosmos) [![许可证](https://img.shields.io/badge/许可证-MIT-green.svg)](LICENSE) [![Python](https://img.shields.io/badge/Python-3.10+-yellow.svg)](https://www.python.org/) [![AstrBot](https://img.shields.io/badge/AstrBot-3.4+-orange.svg)](https://github.com/Soulter/AstrBot) [![jmcomic](https://img.shields.io/badge/jmcomic-≥2.5.38-purple.svg)](https://pypi.org/project/jmcomic/) [![更新日期](https://img.shields.io/badge/更新日期-2025.05.06-lightgrey.svg)](https://github.com/GEMILUXVII/astrbot_plugin_jm_cosmos)

</div>

## 全能型JM漫画下载与管理工具

这是一个用于AstrBot的JM漫画插件，可以下载JM漫画并转换为PDF或图片发送到QQ。

## 功能特性

- 🔍 支持通过ID下载JM漫画并转换为PDF
- 📱 支持发送漫画前几页图片预览
- 🔎 支持搜索漫画、作者作品
- 📊 支持获取漫画排行榜和推荐
- 🌐 支持自动测试和更新可用域名
- 📊 提供详细的PDF文件信息和诊断
- 🔧 可配置代理、Cookie和线程数
- 📁 智能适配各种命名格式的漫画目录
- 🔄 强大的错误处理和故障恢复能力

## 安装方法

1. 下载本插件到AstrBot的插件目录
2. 安装所需依赖：

```bash
pip install -r requirements.txt
```

3. 重启AstrBot
4. 插件将自动加载，所有配置可在AstrBot管理面板的"插件配置"中进行设置
5. 使用`/jmdomain update`命令更新可用域名

## 命令列表

### 基础命令

- `/jm [ID]` - 下载漫画为PDF并发送
- `/jmimg [ID] [页数]` - 发送漫画前几页图片预览
- `/jminfo [ID]` - 查看漫画信息
- `/jmpdf [ID]` - 检查PDF文件信息
- `/jmhelp` - 查看帮助信息

### 搜索功能

- `/jmsearch [关键词] [序号]` - 搜索漫画
- `/jmauthor [作者] [序号]` - 搜索作者作品
- `/jmrecommend` - 随机推荐漫画

### 配置命令

- `/jmconfig proxy [代理URL]` - 设置代理URL
- `/jmconfig noproxy` - 清除代理设置
- `/jmconfig cookie [AVS Cookie]` - 设置登录Cookie
- `/jmconfig threads [数量]` - 设置最大下载线程数
- `/jmconfig domain [域名]` - 添加JM漫画域名
- `/jmconfig debug [on/off]` - 开启/关闭调试模式

### 域名管理

- `/jmdomain list` - 显示当前配置的域名
- `/jmdomain test` - 测试所有域名并显示结果
- `/jmdomain update` - 测试并自动更新可用域名

## 使用示例

1. 下载并发送漫画：
   ```
   /jm 123456
   ```

2. 获取漫画前5页预览：
   ```
   /jmimg 123456 5
   ```

3. 搜索漫画并获取第1个结果：
   ```
   /jmsearch 关键词 1
   ```

4. 设置HTTP代理：
   ```
   /jmconfig proxy http://127.0.0.1:7890
   ```

5. 更新可用域名：
   ```
   /jmdomain update
   ```

## 配置说明

插件使用AstrBot的官方配置系统，配置存储在`data/config/astrbot_plugin_jm_cosmos_config.json`中。您可以通过AstrBot管理面板的"插件配置"页面轻松修改所有设置，也可以使用`/jmconfig`命令进行修改。

配置项包括：

- **domain_list**: JM漫画域名列表
- **proxy**: HTTP代理，如http://127.0.0.1:7890
- **avs_cookie**: 登录Cookie
- **max_threads**: 最大下载线程数
- **debug_mode**: 调试模式开关

## 文件结构

插件核心文件包括：

- `main.py` - 插件入口点和命令注册
- `_conf_schema.json` - 配置模式定义（用于AstrBot管理面板显示）
- `requirements.txt` - 依赖库列表

数据目录位于`AstrBot/data/plugin_data/jm_cosmos/`：
- `downloads/` - 下载的漫画图片目录
- `pdfs/` - 生成的PDF文件目录
- `covers/` - 漫画封面缓存目录
- `logs/` - 日志文件目录

## 高级功能说明

### 智能目录识别

插件支持识别多种目录命名方式：
- 以ID命名的标准目录
- 以漫画标题命名的目录
- 包含ID的混合命名目录
- 自动选择最近修改的包含图片的目录

这意味着即使漫画目录不是以ID命名，命令如`/jmimg`和`/jmpdf`也能正确找到漫画文件。

### PDF诊断功能

`/jmpdf`命令可以：
- 检测文件大小是否超过QQ限制
- 统计主目录和子目录中的所有图片
- 识别章节结构
- 在多种目录结构中查找图片
- 当目录存在但无图片时提供具体提示

## 常见问题

### 1. 漫画无法下载或搜索失败

可能原因：
- 域名失效
- 网络问题
- 爬虫被识别

解决方法：
```
/jmdomain update
```

### 2. 403错误或IP被禁止访问

可能原因：
- IP地区限制
- 爬虫被识别

解决方法：
```
/jmconfig proxy 你的代理地址
```

### 3. 找不到漫画图片

可能原因：
- 漫画目录命名不是ID格式
- 目录结构不规范

解决方法：
- 使用最新版本插件，已支持智能目录识别
- 尝试使用`/jmpdf`命令诊断问题

## 注意事项

1. 本插件仅供学习交流使用
2. 请勿将下载的内容用于商业用途
3. 大量请求可能导致IP被封禁
4. 请遵守当地法律法规

## 更新日志

### v1.0.6
- 更换文件发送方式，修复文件消息缺少参数问题

### v1.0.5
- 迁移到AstrBot官方配置系统，支持在管理面板中配置
- 修复了API兼容性问题，使插件适配AstrBot最新版本
- 优化了资源管理，现在正确使用AstrBot推荐的数据目录
- 改进了错误处理和日志记录
- 添加了线程监控功能，帮助分析性能问题

### v1.0.4
- 增加了智能目录识别功能，支持非标准命名的漫画目录
- 改进了图片统计逻辑，能正确统计主目录和子目录的图片
- 优化了`/jmpdf`命令，提供更详细的图片和章节信息
- 修复了部分漫画因目录命名问题无法使用`/jmimg`命令的问题

### v1.0.3
- 增强了错误处理
- 添加了调试模式
- 添加了网站结构变化的适配
- 修复了PDF文件传输失败问题
- 新增图片预览功能和PDF文件诊断
- 新增域名测试与自动更新功能

### v1.0.2
- 修复了PDF文件传输失败问题
- 新增图片预览功能和PDF文件诊断

### v1.0.1
- 增强了错误处理
- 添加了调试模式
- 添加了网站结构变化的适配

### v1.0.0
- 初始版本发布

## 开发者

[@GEMILUXVII](https://github.com/GEMILUXVII)

## 许可协议

本项目采用MIT许可协议。

## 致谢

本项目基于或参考了以下开源项目:

- [AstrBot](https://github.com/Soulter/AstrBot)
- [JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python)
- [img2pdf](https://github.com/josch/img2pdf)