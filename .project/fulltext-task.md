# 本批全文续接（2026-10-03）

轨道位置：已核题录与入库后复核之后，全文附件验证。R2，因真实文献库附件写入需独立复核。签发：PI 令继续处理已保留两篇，有需其决定的问题再报告；不重复请示。本轮唯一范围：PMID42420446／WD9F8D8E、PMID42816625／IU8CWQD2。

自然语言范围和前四段证据沿用 metadata-trial.md。此轮只为保留项取官方可访问全文，并挂入原父条目；不增题录、不全库改动、不打包插件、不永久删除或合并。原件不修改，父项附件、笔记、标签和目录保留。

实测 Zotero9.0.6，本地API可读；官方本地写接口只适用10+并需独立本地授权。本轮复用已授权云端凭证和官方三段附件上传，无升级或新凭证。运行时复用 E:\Python 的既有 PyMuPDF，不新增解释器或安装包。

已获取两份官方PDF：首篇用现行PMC云元数据的主文pdf_url；第二篇用Nature页面citation_pdf_url，经正常Chrome同源请求。初次静态请求返回HTML而非PDF，记录为失败、不伪装。旧oa.fcgi不再调用；全文XML不会当PDF。

放行标准：下载证据DOI/标题、源PubMed PMID映射及父项一致；PDF首页DOI和标题一致，全部页面可解析、具备研究正文；仅复核keep项可进入下载/挂接；已有附件先读查，服务器文件实际读回且hash一致才成功；同批重跑不新增；失败逐篇可见。真实写前独立离线反例，写后独立证据验收。

边界：本批无真实排除项及旧附件笔记；排除/待核下载拦截、含旧资料保护只作合成反例验证，不能声称真实删除/合并已验证。原始网络失败根因无证据时保留未知。

官方接口依据：
- https://www.zotero.org/support/dev/web_api/v3/local_api
- https://www.zotero.org/support/dev/web_api/v3/file_upload
- https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/
- https://pmc-oa-opendata.s3.amazonaws.com/README.txt
