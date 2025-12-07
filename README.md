AI-evidence-helper-for-security-and-compliance
本项目的用处：利用AI给安全合规证据打标签并写入知识库，再根据知识库使用AI进行检索。可与快速找出上传过的证据。证据支持的格式包括：图片、pdf、文档和表格。

前提：1.安装ollama，gemma3:27b，qwen3-embedding:0.6b
2.安装dify。

注意配置ollama时要在/etc/systemd/system/ollama.service里面加入Environment="OLLAMA_HOST=[docker0 ip]:11434"
对应的dify里面添加ollama model的base url填入http://[docker0 ip]:11434

操作步骤
1. dify工作流-证据导入模块
<img width="3616" height="911" alt="Steven证据库导入助手-whole-workflow" src="https://github.com/user-attachments/assets/2097e740-548e-404b-82d7-4914f0ccd230" />
<img width="933" height="876" alt="条件分支" src="https://github.com/user-attachments/assets/3131bcc4-34a9-417b-9578-08fbdb8e439f" />
<img width="903" height="908" alt="pdf转png" src="https://github.com/user-attachments/assets/70d4539c-aba8-434a-8ca6-08947d3ea96d" />
<img width="906" height="1015" alt="LLM1" src="https://github.com/user-attachments/assets/47ec8302-fe0a-4ed3-a1a2-679c98441513" />
<img width="914" height="946" alt="LLM2" src="https://github.com/user-attachments/assets/49dc2564-bf0b-46b0-a9db-d4de7d29be89" />
<img width="895" height="1015" alt="持久化存储" src="https://github.com/user-attachments/assets/27b9ad98-ef38-4cff-a910-1a375ecafd7c" />

