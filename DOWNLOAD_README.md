# 指数观察：源码与部署

此目录以用户提供的网站源码包为基础，保留收益区间切换、放大字号和手机布局，迁移目标为 `Git-YiDing/index-watch`。

维护说明见 `README.md`，最新部署及核验状态见 `主报告.html`，历史变更见 `CHANGELOG.html`。原站点绑定已移除；GitHub Pages 发布 `site/`。

修改后使用 `conda run -n tmp python scripts/build.py` 构建，最终页面由用户打开验收。
