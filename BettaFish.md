BettaFish/
├── QueryEngine/                            # 国内外新闻广度搜索Agent
│   ├── agent.py                            # Agent主逻辑，协调搜索与分析流程
│   ├── llms/                               # LLM接口封装
│   ├── nodes/                              # 处理节点：搜索、格式化、总结等
│   ├── tools/                              # 国内外新闻搜索工具集
│   ├── utils/                              # 工具函数
│   ├── state/                              # 状态管理
│   ├── prompts/                            # 提示词模板
│   └── ...
├── MediaEngine/                            # 强大的多模态理解Agent
│   ├── agent.py                            # Agent主逻辑，处理视频/图片等多模态内容
│   ├── llms/                               # LLM接口封装
│   ├── nodes/                              # 处理节点：搜索、格式化、总结等
│   ├── tools/                              # 多模态搜索工具集
│   ├── utils/                              # 工具函数
│   ├── state/                              # 状态管理
│   ├── prompts/                            # 提示词模板
│   └── ...
├── InsightEngine/                          # 私有数据库挖掘Agent
│   ├── agent.py                            # Agent主逻辑，协调数据库查询与分析
│   ├── llms/                               # LLM接口封装
│   │   └── base.py                         # 统一的OpenAI兼容客户端
│   ├── nodes/                              # 处理节点：搜索、格式化、总结等
│   │   ├── base_node.py                    # 基础节点类
│   │   ├── search_node.py                  # 搜索节点
│   │   ├── formatting_node.py              # 格式化节点
│   │   ├── report_structure_node.py        # 报告结构节点
│   │   └── summary_node.py                 # 总结节点
│   ├── tools/                              # 数据库查询和分析工具集
│   │   ├── keyword_optimizer.py            # Qwen关键词优化中间件
│   │   ├── search.py                       # 数据库操作工具集（话题搜索、评论获取等）
│   │   └── sentiment_analyzer.py           # 情感分析集成工具
│   ├── utils/                              # 工具函数
│   │   ├── config.py                       # 配置管理
│   │   ├── db.py                           # SQLAlchemy异步引擎与只读查询封装
│   │   └── text_processing.py              # 文本处理工具
│   ├── state/                              # 状态管理
│   │   └── state.py                        # Agent状态定义
│   ├── prompts/                            # 提示词模板
│   │   └── prompts.py                      # 各类提示词
│   └── __init__.py
├── ReportEngine/                           # 多轮报告生成Agent
│   ├── agent.py                            # 总调度器：模板选择→布局→篇幅→章节→渲染
│   ├── flask_interface.py                  # Flask/SSE入口，管理任务排队与流式事件
│   ├── llms/                               # OpenAI兼容LLM封装
│   │   └── base.py                         # 统一的流式/重试客户端
│   ├── core/                               # 核心功能：模板解析、章节存储、文档装订
│   │   ├── template_parser.py              # Markdown模板切片与slug生成
│   │   ├── chapter_storage.py              # 章节run目录、manifest与raw流写入
│   │   └── stitcher.py                     # Document IR装订器，补齐锚点/元数据
│   ├── ir/                                 # 报告中间表示（IR）契约与校验
│   │   ├── schema.py                       # 块/标记Schema常量定义
│   │   └── validator.py                    # 章节JSON结构校验器
│   ├── nodes/                              # 全流程推理节点
│   │   ├── base_node.py                    # 节点基类+日志/状态钩子
│   │   ├── template_selection_node.py      # 模板候选收集与LLM筛选
│   │   ├── document_layout_node.py         # 标题/目录/主题设计
│   │   ├── word_budget_node.py             # 篇幅规划与章节指令生成
│   │   └── chapter_generation_node.py      # 章节级JSON生成+校验
│   ├── prompts/                            # 提示词库与Schema说明
│   │   └── prompts.py                      # 模板选择/布局/篇幅/章节提示词
│   ├── renderers/                          # IR渲染器
│   │   ├── html_renderer.py                # Document IR→交互式HTML
│   │   ├── pdf_renderer.py                 # HTML→PDF导出（WeasyPrint）
│   │   ├── pdf_layout_optimizer.py         # PDF布局优化器
│   │   └── chart_to_svg.py                 # 图表转SVG工具
│   ├── state/                              # 任务/元数据状态模型
│   │   └── state.py                        # ReportState与序列化工具
│   ├── utils/                              # 配置与辅助工具
│   │   ├── config.py                       # Pydantic Settings与打印助手
│   │   ├── dependency_check.py             # 依赖检查工具
│   │   ├── json_parser.py                  # JSON解析工具
│   │   ├── chart_validator.py              # 图表校验工具
│   │   └── chart_repair_api.py             # 图表修复API
│   ├── report_template/                    # Markdown模板库
│   │   ├── 企业品牌声誉分析报告.md
│   │   └── ...
│   └── __init__.py
├── ForumEngine/                            # 论坛引擎：Agent协作机制
│   ├── monitor.py                          # 日志监控和论坛管理核心
│   ├── llm_host.py                         # 论坛主持人LLM模块
│   └── __init__.py
├── MindSpider/                             # 社交媒体爬虫系统
│   ├── main.py                             # 爬虫主程序入口
│   ├── config.py                           # 爬虫配置文件
│   ├── BroadTopicExtraction/               # 话题提取模块
│   │   ├── main.py                         # 话题提取主程序
│   │   ├── database_manager.py             # 数据库管理器
│   │   ├── get_today_news.py               # 今日新闻获取
│   │   └── topic_extractor.py              # 话题提取器
│   ├── DeepSentimentCrawling/              # 深度舆情爬取模块
│   │   ├── main.py                         # 深度爬取主程序
│   │   ├── keyword_manager.py              # 关键词管理器
│   │   ├── platform_crawler.py             # 平台爬虫管理
│   │   └── MediaCrawler/                   # 社媒爬虫核心
│   │       ├── main.py
│   │       ├── config/                     # 各平台配置
│   │       ├── media_platform/             # 各平台爬虫实现
│   │       └── ...
│   └── schema/                             # 数据库结构定义
│       ├── db_manager.py                   # 数据库管理器
│       ├── init_database.py                # 数据库初始化脚本
│       ├── mindspider_tables.sql           # 数据库表结构SQL
│       ├── models_bigdata.py               # 大规模媒体舆情表的SQLAlchemy映射
│       └── models_sa.py                    # DailyTopic/Task等扩展表ORM模型
├── SentimentAnalysisModel/                 # 情感分析模型集合
│   ├── WeiboSentiment_Finetuned/           # 微调BERT/GPT-2模型
│   │   ├── BertChinese-Lora/               # BERT中文LoRA微调
│   │   │   ├── train.py
│   │   │   ├── predict.py
│   │   │   └── ...
│   │   └── GPT2-Lora/                      # GPT-2 LoRA微调
│   │       ├── train.py
│   │       ├── predict.py
│   │       └── ...
│   ├── WeiboMultilingualSentiment/         # 多语言情感分析
│   │   ├── train.py
│   │   ├── predict.py
│   │   └── ...
│   ├── WeiboSentiment_SmallQwen/           # 小参数Qwen3微调
│   │   ├── train.py
│   │   ├── predict_universal.py
│   │   └── ...
│   └── WeiboSentiment_MachineLearning/     # 传统机器学习方法
│       ├── train.py
│       ├── predict.py
│       └── ...
├── SingleEngineApp/                        # 单独Agent的Streamlit应用
│   ├── query_engine_streamlit_app.py       # QueryEngine独立应用
│   ├── media_engine_streamlit_app.py       # MediaEngine独立应用
│   └── insight_engine_streamlit_app.py     # InsightEngine独立应用
├── query_engine_streamlit_reports/         # QueryEngine单应用运行输出
├── media_engine_streamlit_reports/         # MediaEngine单应用运行输出
├── insight_engine_streamlit_reports/       # InsightEngine单应用运行输出
├── templates/                              # Flask前端模板
│   └── index.html                          # 主界面HTML
├── static/                                 # 静态资源
│   └── image/                              # 图片资源
│       ├── logo_compressed.png
│       ├── framework.png
│       └── ...
├── logs/                                   # 运行日志目录
├── final_reports/                          # 最终生成的报告文件
│   ├── ir/                                 # 报告IR JSON文件
│   └── *.html                              # 最终HTML报告
├── utils/                                  # 通用工具函数
│   ├── forum_reader.py                     # Agent间论坛通信工具
│   ├── github_issues.py                    # 统一生成GitHub Issue链接与错误提示
│   └── retry_helper.py                     # 网络请求重试机制工具
├── tests/                                  # 单元测试与集成测试
│   ├── run_tests.py                        # pytest入口脚本
│   ├── test_monitor.py                     # ForumEngine监控单元测试
│   ├── test_report_engine_sanitization.py  # ReportEngine安全性测试
│   └── ...
├── app.py                                  # Flask主应用入口
├── config.py                               # 全局配置文件
├── .env.example                            # 环境变量示例文件
├── docker-compose.yml                      # Docker多服务编排配置
├── Dockerfile                              # Docker镜像构建文件
├── requirements.txt                        # Python依赖包清单
├── regenerate_latest_pdf.py                # PDF重新生成工具脚本
├── report_engine_only.py                   # Report Engine命令行版本
├── README.md                               # 中文说明文档
├── README-EN.md                            # 英文说明文档
├── CONTRIBUTING.md                         # 中文贡献指南
├── CONTRIBUTING-EN.md                      # 英文贡献指南
└── LICENSE                                 # GPL-2.0开源许可证