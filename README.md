# 指数观察 · Index Watch

展示标准标普500与纳斯达克100人民币场外基金的申购状态、公开参考限额、列示年费及历史累计收益。保留暂停申购基金，排除等权重、增强、行业主题、杠杆反向、美元份额与直接在交易所买卖的ETF。

- 仓库：https://github.com/Git-YiDing/index-watch
- GitHub Pages目标地址：https://git-yiding.github.io/index-watch/
- 部署进度、核验结果及时间：见 [主报告.html](主报告.html) 和 [CHANGELOG.html](CHANGELOG.html)。
- 每日计划：北京时间08:17、14:17，由 [GitHub Actions](https://github.com/Git-YiDing/index-watch/actions/workflows/daily.yml) 执行；GitHub调度可能延迟或停用，以实际运行日志和字段日期为准。

## 数据边界

人工白名单共53个份额，其中标普500为14个、纳斯达克100为39个。范围由 `config/catalog.json` 控制，新基金须核对产品文件后人工加入。

**公开参考额度与支付宝核验额度分开。** 自动采集读取天天基金公开页面，不能据此确认支付宝可买。支付宝授权数据源尚未接入；该列保持待核验。渠道证据须包含有效时间、来源及有效期，最长36小时；过期和未知状态不视为无限额。

固定年费是管理费率、托管费率、销售服务费率的合计，数据中的0.65表示每年0.65%。它不含申购、赎回、交易及其他运作费用；ETF联接和FOF的实际穿透费用需按合同判断。来源拆分缺失时不反推或补零。代码160213的来源销售服务费缺失，保留待核验并在健康状态中告警。

历史收益列支持1至5年及全部可得历史，按单位净值及现金分红再投资计算，是累计收益而非年化收益。历史不足时保留未知。起止日期、来源及方法可在基金详情中查看。

采集失败保留原值与原核验日期。公开申购状态超过36小时提示待更新，费率超过90天提示复核。站点不执行交易。

## 每日流程与发布

`.github/workflows/daily.yml` 在main分支推送、手动触发和每日两个计划时点运行。流程依次执行单元测试、额度费率采集、收益采集、数据校验、静态构建、保存观测、GitHub Pages发布和采集完整性检查。更新数据由GitHub自带的 `GITHUB_TOKEN` 提交，不依赖本机登录凭据。

部分采集失败时，网站仍发布真实状态，工作流最后以失败提示需要检查；页面发布步骤与数据完整性检查需要分别查看。缺失值不会被替换成虚构的可买额度或零费率。

Pages发布源须为GitHub Actions，运行时需要 `contents: write`、`pages: write`、`id-token: write`。源码和维护报告放在仓库根目录；仅 `site/` 进入Pages发布产物。原包的 `dist/` 为Sites导出副本，不参与此部署。

如有合法的支付宝结构化数据源，可设置仓库Secret `ALIPAY_FEED_URL`；人工证据可写入 `config/alipay-overrides.json`。仅有接口入口不代表本项目提供支付宝官方API。不要提交密码、Cookie、令牌或个人账户信息。

## 本地维护

所有Python命令在已有Conda `tmp` 环境执行。若需安装依赖，只安装到该环境。

```bash
conda run -n tmp python -m pip install --no-user -r requirements.txt
conda run -n tmp python -m unittest discover -s tests -v
conda run -n tmp python scripts/update.py
conda run -n tmp python scripts/update_returns.py
conda run -n tmp python scripts/validate.py
conda run -n tmp python scripts/build.py
node --check site/assets/app.js
```

`site/index.html` 可由用户离线打开；线上页面优先读取同目录 `data/` 的快照。修改模板、样式、脚本或数据后重新构建。生产维护不重跑 `scripts/seed.py`，避免将当前观测恢复为首版数据。

本地验证使用单元测试、静态语法及HTTP检查；遵循项目规则，不执行浏览器或GUI自动化。用户自行验收最终视觉布局。

| 内容 | 文件 |
|---|---|
| 页面、样式、交互 | `site/template.html`、`site/assets/` |
| 基金白名单 | `config/catalog.json` |
| 支付宝人工核验 | `config/alipay-overrides.json` |
| 额度和费率采集 | `scripts/update.py` |
| 历史收益采集 | `scripts/update_returns.py` |
| 校验与构建 | `scripts/validate.py`、`scripts/build.py` |
| 每日采集发布 | `.github/workflows/daily.yml` |

## 来源

- [天天基金公开费率与申购状态](https://fundf10.eastmoney.com/jjfl_019172.html)
- [天天基金公开净值历史](https://fund.eastmoney.com/019172.html)
- [GitHub Pages工作流说明](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [Conda环境工作流动作](https://github.com/conda-incubator/setup-miniconda)

每个份额的具体来源与核验时间随数据保存。来源改变、抓取失败或字段缺失时保留并展示真实状态。
