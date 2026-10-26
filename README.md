# 指数观察 · Index Watch

展示标准标普500与纳斯达克100人民币场外基金的申购状态、公开参考限额、列示年费及历史累计收益。保留暂停申购基金，排除等权重、增强、行业主题、杠杆反向、美元份额与直接在交易所买卖的ETF。

- 仓库：https://github.com/Git-YiDing/index-watch
- 已上线网站：https://git-yiding.github.io/index-watch/
- 部署进度、核验结果及时间：见 [主报告.html](主报告.html) 和 [CHANGELOG.html](CHANGELOG.html)。
- 每日计划：北京时间08:17、14:17，由 [GitHub Actions](https://github.com/Git-YiDing/index-watch/actions/workflows/daily.yml) 执行；GitHub调度可能延迟或停用，以实际运行日志和字段日期为准。

## 已完成部署核验

2026-10-26 16:07（本机时间）确认滚动定投新列已上线，7个公网资源返回HTTP 200。63项单元测试、51项无浏览器交互检查、197个有效窗口的独立份额账本复核通过。53个份额均以当前北京时间日期回溯窗口；近1年53、近2年49、近3年42、全部53个份额可计算，其余区间历史不足。

[本次线上运行](https://github.com/Git-YiDing/index-watch/actions/runs/40336247901)已完成每日数据采集、滚动定投计算和发布。160213销售服务费缺失，最终完整性检查告警导致运行总状态为failure；Publish步骤成功。

## 数据边界

人工白名单共53个份额，其中标普500为14个、纳斯达克100为39个。范围由 `config/catalog.json` 控制，新基金须核对产品文件后人工加入。

**公开参考额度与支付宝核验额度分开。** 自动采集读取天天基金公开页面，不能据此确认支付宝可买。支付宝授权数据源尚未接入；该列保持待核验。渠道证据须包含有效时间、来源及有效期，最长36小时；过期和未知状态不视为无限额。

固定年费是管理费率、托管费率、销售服务费率的合计，数据中的0.65表示每年0.65%。它不含申购、赎回、交易及其他运作费用；ETF联接和FOF的实际穿透费用需按合同判断。来源拆分缺失时不反推或补零。代码160213的来源销售服务费缺失，保留待核验并在健康状态中告警。

历史收益列支持1至5年及全部可得历史，按单位净值及现金分红再投资计算，是累计收益而非年化收益。历史不足时保留未知。起止日期、来源及方法可在基金详情中查看。

## 每日100元模拟定投

新增独立定投列，可切换近1年、近2年、近3年与全部历史，按累计收益率排序；每行显示累计收益率、盈亏和估值日。详情提供累计投入、估算市值、投入次数、窗口与实际投入日期；CSV包含所选区间的完整字段。

窗口以每次采集时的北京时间当天回溯1、2、3个日历年，包含起止日，2月29日回溯到非闰年取2月28日。所有份额使用同一天作为窗口基准，不以最新净值日回推，也不固定为某个历史起始日。“全部”从该份额最早可得净值日起算。

每个周一至周五且有有效净值的日期，按当日净值投入100元；无净值日期跳过，周末调休不投入。现金分红按除息日净值再投资，新投入从买入之后参与收益。估值使用最新已披露净值，未披露日期不补投。累计收益率为累计盈亏除以累计投入，是累计收益而非年化或内部收益率。

这是历史模拟，未计个人申购赎回费用及历史限购、暂停申购状态；有净值不等于实际可申购。历史不足、净值大段缺失及未识别份额变动显示未知。采集失败保留原结果与窗口基准日期，页面标注更新失败或待更新。

结果保存在 `site/data/returns.json` 的各份额 `dca` 字段，复用已有每日采集，不新增第三方接口。`scripts/validate.py` 校验滚动日期、投入次数、金额及收益之间的一致性。无浏览器交互检查入口为 `tests/returns_dom_smoke.cjs`，测试依赖 `linkedom` 仅安装在Conda tmp环境内。

采集失败保留原值与原核验日期。公开申购状态超过36小时提示待更新，费率超过90天提示复核。站点不执行交易。

## 每日流程与发布

`.github/workflows/daily.yml` 在main分支推送、手动触发和每日两个计划时点运行。流程依次执行单元测试、额度费率采集、收益与滚动定投采集、数据校验、静态构建、保存观测、GitHub Pages发布和采集完整性检查。更新数据由GitHub自带的 `GITHUB_TOKEN` 提交，不依赖本机登录凭据。

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
