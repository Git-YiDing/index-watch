(() => {
  'use strict';
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const paths = {
    moon:'M20.9 13A9 9 0 0 1 11 3.1 9 9 0 1 0 20.9 13Z',
    sun:'M12 3v2m0 14v2M3 12h2m14 0h2M5.6 5.6 7 7m10 10 1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z',
    layers:'m12 3 10 6-10 6L2 9l10-6Zm-10 12 10 6 10-6M2 12l10 6 10-6',
    info:'M12 11v6m0-10h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z',
    refresh:'M20 7v5h-5M4 17v-5h5M6.1 6.1a8 8 0 0 1 12.8 2L20 12M4 12l1.1 3.9a8 8 0 0 0 12.8 2',
    download:'M12 3v12m-5-5 5 5 5-5M4 15v5h16v-5',
    search:'m21 21-4.4-4.4M19 11a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z',
    shield:'M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3Zm-4 9 3 3 5-6',
    calculator:'M6 3h12v18H6V3Zm3 4h6M9 12h.01M15 12h.01M9 16h.01M15 16h.01',
    'check-circle':'m8 12 3 3 5-6M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z',
    x:'m6 6 12 12M6 18 18 6',
    copy:'M9 9h11v12H9V9ZM5 15H3V3h12v2',
    arrow:'M7 17 17 7M7 7h10v10'
  };
  const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name] || paths.info}"/></svg>`;
  const icons = (root = document) => $$('[data-icon]', root).forEach(el => { el.innerHTML = icon(el.dataset.icon); });
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const url = value => { try { const u = new URL(value); return u.protocol === 'https:' ? u.href : ''; } catch { return ''; } };
  const numeric = value => typeof value === 'number' && Number.isFinite(value);
  const num = value => numeric(value) ? value.toLocaleString('zh-CN', {maximumFractionDigits:2}) : '—';
  const rate = value => numeric(value) ? `${value.toFixed(2)}%` : '待核验';
  const date = value => value ? String(value).slice(0, 10) : '未核验';
  const time = value => value ? String(value).replace('T',' ').replace(/\+08:00$/, ' 北京时间') : '尚未运行';
  const timeMs = value => !value ? NaN : Date.parse(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00+08:00` : value);
  const boot = JSON.parse($('#seed-data').textContent);
  let dataset = boot.dataset;
  let health = boot.health;
  let history = boot.history;
  let returnsData = boot.returns || {funds:{}};
  const RETURN_LABELS = {'1y':'近1年','2y':'近2年','3y':'近3年','4y':'近4年','5y':'近5年',all:'全部历史'};
  const DCA_LABELS = {'1y':'近1年','2y':'近2年','3y':'近3年',all:'全部历史'};
  const shanghaiToday = () => new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  let state = {index:'all', status:'all', cls:'all', query:'', sort:'smart', verified:false, page:1, period:'1y', dcaPeriod:'1y'};
  const PAGE_SIZE = 10;
  let returnFocus = null, toastTimer;
  const expired = r => Boolean(r.observed_at) && (Date.now()-timeMs(r.observed_at)) > (dataset.meta.reference_ttl_hours || 36)*3600000;
  const feeExpired = f => Boolean(f.fees.checked_at) && (Date.now()-timeMs(f.fees.checked_at)) > (dataset.meta.fee_ttl_days || 90)*86400000;
  const alipayVerified = f => {
    const a = f.alipay || {};
    const t = timeMs(a.checked_at), e = timeMs(a.expires_at), now = Date.now();
    return ['limited','open','paused'].includes(a.status) && a.scope === 'alipay' && !!url(a.evidence_url) && Number.isFinite(t) && Number.isFinite(e) && t <= now + 300000 && now <= e && now-t <= 36*3600000;
  };
  const indexLabel = f => f.index === 'sp500' ? '标普500' : '纳指100';
  const returnRecord = f => returnsData.funds?.[f.code] || {};
  const periodReturn = (f, period=state.period) => returnRecord(f).periods?.[period] || {};
  const signedReturn = value => `${value>0?'+':''}${value.toFixed(2)}%`;
  const returnClass = value => value>0?'return-positive':value<0?'return-negative':'return-neutral';
  const dcaRecord = f => returnRecord(f).dca || {};
  const dcaPeriod = (f, period=state.dcaPeriod) => dcaRecord(f).periods?.[period] || {};
  const signedMoney = value => `${value>0?'+':''}${num(value)}元`;
  function dcaCell(f) {
    const record=returnRecord(f),dca=dcaRecord(f),item=dcaPeriod(f);
    if(!numeric(item.value))return `<span class="muted-value">—</span><span class="cell-sub">${esc(item.reason || '暂无定投数据')}</span>`;
    const stale=dca.basis_date!==shanghaiToday();
    return `<button class="return-value dca-value ${returnClass(item.value)}" data-detail="${esc(f.code)}" aria-label="${esc(f.name)}，${DCA_LABELS[state.dcaPeriod]}每日100元模拟定投收益率 ${signedReturn(item.value)}，查看详情">${signedReturn(item.value)}</button><span class="cell-sub ${returnClass(item.profit)}">盈亏 ${signedMoney(item.profit)}</span><span class="cell-sub">估值 ${esc(item.valuation_date)}</span>${record.error||stale?`<span class="cell-sub error-color">${record.error?'更新失败':'待更新'} · 基准 ${esc(dca.basis_date)}</span>`:''}`;
  }
  function dcaDetails(f) {
    const record=returnRecord(f),dca=dcaRecord(f);
    return `<h3>每日定投100元 <span class="return-detail-tag">模拟 · 累计收益</span></h3><p class="detail-note">窗口基准：${esc(dca.basis_date || '未计算')}（北京时间）。近1、2、3年均从此日期向前回溯；估值截至已披露净值日。</p><div class="dca-detail-grid">${Object.entries(DCA_LABELS).map(([key,label])=>{
      const item=dcaPeriod(f,key),known=numeric(item.value);
      return `<div class="${key===state.dcaPeriod?'selected-dca':''}"><span>${label}</span><strong class="${known?returnClass(item.value):'muted-value'}">${known?signedReturn(item.value):'—'}</strong>${known?`<p class="${returnClass(item.profit)}">累计盈亏 ${signedMoney(item.profit)}</p><dl><div><dt>累计投入</dt><dd>¥${num(item.invested)}</dd></div><div><dt>估算市值</dt><dd>¥${num(item.market_value)}</dd></div><div><dt>投入次数</dt><dd>${num(item.contribution_count)}次</dd></div></dl>`:`<p>${esc(item.reason || '暂无定投数据')}</p>`}<small>窗口：${esc(item.requested_start || '—')} 至 ${esc(item.requested_end || '—')}</small>${known?`<small>投入：${esc(item.first_contribution)} 至 ${esc(item.last_contribution)}</small>`:''}<small>净值估值：${esc(item.valuation_date || '—')}</small></div>`;
    }).join('')}</div><p class="detail-note">周一至周五且有净值的日期按当日净值投入100元，无净值日期跳过。分红再投资；累计收益率为累计盈亏除以累计投入，非年化。未计个人申赎费及历史限购、暂停申购；这是一项历史模拟。净值尚未披露的日期不补投。</p>${dca.basis_date&&dca.basis_date!==shanghaiToday()?'<p class="detail-note error-color">窗口基准尚未更新到今天，以上保留原日期的模拟结果。</p>':''}${record.error?`<p class="detail-note error-color">${esc(record.error)}</p>`:''}`;
  }
  function returnCell(f) {
    const record=returnRecord(f), item=periodReturn(f);
    if(!numeric(item.value))return `<span class="muted-value">—</span><span class="cell-sub">${esc(item.reason || '暂无数据')}</span>`;
    const older=Date.now()-timeMs(record.as_of)>14*86400000;
    return `<button class="return-value ${returnClass(item.value)}" data-detail="${esc(f.code)}" aria-label="${esc(f.name)}，${RETURN_LABELS[state.period]}累计收益率 ${signedReturn(item.value)}，查看各区间详情">${signedReturn(item.value)}</button><span class="cell-sub">${record.error?'更新失败 · ':older?'历史快照 · ':'截至 '}${esc(record.as_of || item.end_date)}</span>`;
  }
  function returnDetails(f) {
    const record=returnRecord(f);
    return `<h3>历史区间收益率 <span class="return-detail-tag">累计 · 非年化</span></h3><div class="return-detail-grid">${Object.entries(RETURN_LABELS).map(([key,label])=>{
      const item=periodReturn(f,key);
      return `<div><span>${label==='全部历史'?'全部（可得历史）':label}</span><strong class="${numeric(item.value)?returnClass(item.value):'muted-value'}">${numeric(item.value)?signedReturn(item.value):'—'}</strong><small>${esc(numeric(item.value)?`${item.start_date} 至 ${item.end_date}`:item.reason || '暂无数据')}</small></div>`;
    }).join('')}</div><p class="detail-note">按人民币净值计算，现金分红按除息日净值再投资；不含个人申购赎回费用。全部从该份额最早可得净值日起算，不保证等于法律成立日。各份额净值截止日可能不同，历史不足的区间不补算。</p>${record.error?`<p class="detail-note error-color">${esc(record.error)}</p>`:''}${record.source_url?sourceRow(record.source_label,record.source_url,record.as_of):''}`;
  }
  function referenceState(f) {
    const r = f.reference;
    if (r.verification === 'historical') return {key:'paused', label:'暂停记录', sub:'历史状态待复核', cls:'unknown', usable:false};
    if (r.error || expired(r)) return {key:r.status === 'paused' ? 'paused':'unknown', label:'待更新', sub:r.error ? '最近采集失败':'快照已过期', cls:'stale', usable:false};
    if (r.status === 'limited') return {key:'available', label:'限额申购', sub:r.verification === 'page' ? '天天基金口径':'公开汇总口径', cls:'', usable:true};
    if (r.status === 'open') return {key:'available', label:'开放申购', sub:'公开渠道口径', cls:'', usable:true};
    if (r.status === 'paused') return {key:'paused', label:'暂停申购', sub:r.verification === 'page' ? '天天基金口径':'公开汇总口径', cls:'paused', usable:false};
    return {key:'unknown', label:'待核验', sub:r.verification === 'conflicting' ? '公开来源冲突':'额度未确认', cls:'unknown', usable:false};
  }
  function toast(message) { clearTimeout(toastTimer); $('#toast').textContent=message; $('#toast').classList.add('visible'); toastTimer=setTimeout(()=>$('#toast').classList.remove('visible'),3000); }
  async function copyCode(code) {
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(code);
      else {
        const el=document.createElement('textarea'); el.value=code; el.style.position='fixed'; el.style.opacity='0'; document.body.appendChild(el);el.select();
        const success=document.execCommand('copy');el.remove();if(!success) throw new Error('copy denied');
      }
      toast(`已复制 ${code}，可粘贴到支付宝搜索`);
    } catch { toast(`无法自动复制，基金代码：${code}`); }
  }
  function getRows() {
    let rows = dataset.funds.filter(f => {
      const q = state.query.toLowerCase().replace(/\s+/g,'');
      const hay = `${f.name}${f.code}${f.manager}${f.benchmark}${indexLabel(f)}`.toLowerCase().replace(/\s+/g,'');
      return (state.index==='all'||f.index===state.index) && (!q || hay.includes(q)) && (state.cls==='all'||(state.cls==='other'?!['A','C'].includes(f.share_class):f.share_class===state.cls)) && (state.status==='all'||referenceState(f).key===state.status) && (!state.verified||alipayVerified(f));
    });
    const cmpFee=(a,b,desc=false) => {
      const x=a.fees.total,y=b.fees.total;
      if (!numeric(x) && !numeric(y)) return a.code.localeCompare(b.code);
      if (!numeric(x)) return 1;if (!numeric(y)) return -1;
      return (desc ? y-x : x-y) || a.code.localeCompare(b.code);
    };
    rows.sort((a,b) => {
      if(state.sort==='fee-asc')return cmpFee(a,b);
      if(state.sort==='fee-desc')return cmpFee(a,b,true);
      if(state.sort==='code')return a.code.localeCompare(b.code);
      if(state.sort==='dca-desc'||state.sort==='dca-asc'){
        const x=dcaPeriod(a).value,y=dcaPeriod(b).value;
        if(!numeric(x)&&!numeric(y))return a.code.localeCompare(b.code);
        if(!numeric(x))return 1;if(!numeric(y))return -1;
        return (state.sort==='dca-desc'?y-x:x-y)||a.code.localeCompare(b.code);
      }
      if(state.sort==='return-desc'||state.sort==='return-asc'){
        const x=periodReturn(a).value,y=periodReturn(b).value;
        if(!numeric(x)&&!numeric(y))return a.code.localeCompare(b.code);
        if(!numeric(x))return 1;if(!numeric(y))return -1;
        return (state.sort==='return-desc'?y-x:x-y)||a.code.localeCompare(b.code);
      }
      if(state.sort==='limit-desc'){
        const x=referenceState(a).usable&&numeric(a.reference.daily_limit)?a.reference.daily_limit:-1;
        const y=referenceState(b).usable&&numeric(b.reference.daily_limit)?b.reference.daily_limit:-1;
        return y-x||cmpFee(a,b);
      }
      const rank={available:0,unknown:1,paused:2};
      return rank[referenceState(a).key]-rank[referenceState(b).key]||cmpFee(a,b);
    });
    return rows;
  }
  function renderOverview() {
    for(const [key,prefix] of [['sp500','sp'],['nasdaq100','ndx']]){
      const rows=dataset.funds.filter(f=>f.index===key);
      $(`#${prefix}-count`).textContent=rows.length;
      const limited=rows.filter(f=>referenceState(f).usable).length,paused=rows.filter(f=>referenceState(f).key==='paused').length;
      $(`#${prefix}-foot`).innerHTML=`<span class="green-text">${limited} 个参考可申购</span><i></i><span>${paused} 个暂停记录</span>`;
      $(`#tab-${prefix}`).textContent=rows.length;
    }
    $('#total-count').textContent=dataset.funds.length;$('#tab-all').textContent=dataset.funds.length;
    $('#snapshot-badge').textContent=`快照 ${date(dataset.meta.snapshot_date)}`;
    $('#snapshot-date').textContent=date(dataset.meta.snapshot_date);
    const verified=dataset.funds.filter(alipayVerified).length;
    $('#verified-count').textContent=`${verified} / ${dataset.funds.length}`;
    $('#trust-progress').style.width=`${verified/dataset.funds.length*100}%`;
    $('#fee-coverage').textContent=`${dataset.funds.filter(f=>numeric(f.fees.total)).length} / ${dataset.funds.length}`;
    if(verified) $('#trust-copy').textContent='已核验记录附有渠道证据及有效期。其余记录仍仅作公开参考，不代表支付宝可买。';
    $('#health-state').textContent=health.status==='not_deployed'?'预览 · 未部署':health.status==='ok'?'采集正常':health.status==='partial'?'部分采集失败':'采集失败';
    $('#run-badge').textContent=health.status==='not_deployed'?'首版预览':health.status==='ok'?'已生成快照':'需检查数据';
    $('#run-badge').className=`chip ${health.status==='ok'?'':'amber'}`;
    $('#run-description').textContent=health.status==='not_deployed'?'更新任务尚未部署':`最近检查 ${date(health.last_attempt_at)}`;
  }
  function quotaHTML(f) {
    const r=f.reference,s=referenceState(f);
    if(r.status==='paused')return '<span class="muted-value">—</span><span class="cell-sub">暂停记录，不计额度</span>';
    if(!s.usable)return `<span class="muted-value">—</span><span class="cell-sub">${s.cls==='stale'?'等待重新核验':'不视为不限购'}</span>`;
    if(numeric(r.daily_limit))return `<span class="quota-number"><span class="currency">¥</span>${num(r.daily_limit)}</span><span class="cell-sub">每账户 / 日 · 参考</span>`;
    return `<span class="muted-value">${r.unlimited===true?'不限额':'未披露'}</span><span class="cell-sub">仅限公开来源口径</span>`;
  }
  function renderTable() {
    $('#dca-heading-label').textContent=`${DCA_LABELS[state.dcaPeriod]}定投`;
    $('.dca-heading').setAttribute('aria-sort',state.sort==='dca-desc'?'descending':state.sort==='dca-asc'?'ascending':'none');
    $('#dca-sort-icon').textContent=state.sort==='dca-desc'?'↓':state.sort==='dca-asc'?'↑':'↕';
    $('#dca-window-note').textContent=`目标窗口基准 ${shanghaiToday()} · 北京时间`;
    $('#return-heading-label').textContent=`${RETURN_LABELS[state.period]}收益率`;
    $('.return-heading').setAttribute('aria-sort',state.sort==='return-desc'?'descending':state.sort==='return-asc'?'ascending':'none');
    $('#return-sort-icon').textContent=state.sort==='return-desc'?'↓':state.sort==='return-asc'?'↑':'↕';
    const rows=getRows(), pages=Math.max(1,Math.ceil(rows.length/PAGE_SIZE));state.page=Math.min(state.page,pages);
    const visible=rows.slice((state.page-1)*PAGE_SIZE,state.page*PAGE_SIZE);
    $('#fund-rows').innerHTML=visible.map(f=>{
      const s=referenceState(f),a=alipayVerified(f),fee=f.fees.total;
      const channel=a?(f.alipay.status==='paused'?'已核验 · 暂停':numeric(f.alipay.daily_limit)?`已核验 ¥${num(f.alipay.daily_limit)}`:'已核验 · 见详情'):'待核验';
      return `<tr data-row="${esc(f.code)}"><td><div class="fund-main"><button class="fund-name" data-detail="${esc(f.code)}">${esc(f.name.replace(/ [ACDEI]$/,''))}<span class="class-badge">${esc(f.share_class)}</span></button></div><div class="fund-meta"><button class="fund-code" data-copy="${esc(f.code)}" title="复制基金代码" aria-label="复制基金代码 ${esc(f.code)}">${esc(f.code)}${icon('copy')}</button><span class="index-pill ${f.index==='nasdaq100'?'ndx':''}">${indexLabel(f)}</span></div></td><td data-label="公开参考状态"><span class="status-badge ${s.cls}"><i class="dot ${s.cls?'gray':'green'}"></i>${s.label}</span><span class="status-sub">${s.sub}</span></td><td class="number-cell" data-label="参考日限额">${quotaHTML(f)}</td><td class="number-cell" data-label="固定年费">${numeric(fee)?`<span class="rate-number">${fee.toFixed(2)}<span>%</span></span><span class="cell-sub">${(feeExpired(f)||f.fees.error)?'费率需复核':f.fees.verification==='page'?'已读取费率页':'公开汇总 · 待复核'}</span>`:'<span class="muted-value">—</span><span class="cell-sub">费率待采集</span>'}</td><td class="number-cell return-cell" data-label="${RETURN_LABELS[state.period]}收益率">${returnCell(f)}</td><td class="number-cell dca-cell" data-label="${DCA_LABELS[state.dcaPeriod]}每日定投100元">${dcaCell(f)}</td><td class="channel-cell" data-label="支付宝核验"><button class="channel-label ${a?'verified':''}" data-detail="${esc(f.code)}">${esc(channel)}</button></td><td><button class="row-more" data-detail="${esc(f.code)}" aria-label="查看 ${esc(f.name)} 详情">↗</button></td></tr>`;
    }).join('');
    $('#empty-state').hidden=rows.length!==0;
    $('#empty-description').textContent=state.verified?'当前没有符合筛选条件且仍在有效期内的支付宝渠道核验记录。取消此筛选，可查看公开参考数据。':'试试更换关键词或筛选条件。';
    $('#result-count').textContent=rows.length?`显示 ${(state.page-1)*PAGE_SIZE+1}–${Math.min(state.page*PAGE_SIZE,rows.length)}，共 ${rows.length} 个份额`:'0 个符合条件的份额';
    $('#page-label').textContent=`${state.page} / ${pages}`;$('#prev-page').disabled=state.page<=1;$('#next-page').disabled=state.page>=pages;
    $$('[data-tab]').forEach(b=>{const active=b.dataset.tab===state.index;b.classList.toggle('selected',active);b.setAttribute('aria-selected',String(active));});
    $$('[data-status]').forEach(b=>b.classList.toggle('chosen',b.dataset.status===state.status));
  }
  function update(patch) { Object.assign(state,patch,{page:1});renderTable(); }
  function renderCalculator() {
    const old=$('#calc-fund').value;
    const known=dataset.funds.filter(f=>numeric(f.fees.total)).sort((a,b)=>a.fees.total-b.fees.total||a.code.localeCompare(b.code));
    $('#calc-fund').innerHTML=known.map(f=>`<option value="${esc(f.code)}">${esc(f.name)} · ${rate(f.fees.total)}</option>`).join('');
    if(known.some(f=>f.code===old))$('#calc-fund').value=old;
    else if(known.some(f=>f.code==='019172'))$('#calc-fund').value='019172';
    calculate();
  }
  function calculate() {
    const f=dataset.funds.find(f=>f.code===$('#calc-fund').value);const n=Number($('#principal').value);
    if(!f||!Number.isFinite(n)||n<0||n>1e9){$('#calc-result').textContent='—';$('#calc-equation').textContent='请输入 0 至 10 亿之间的金额';return;}
    $('#calc-result').textContent=num(n*f.fees.total/100);$('#calc-equation').textContent=`¥${num(n)} × ${rate(f.fees.total)} / 年`;
  }
  function showDialog(dialog) {returnFocus=document.activeElement;dialog.showModal();icons(dialog);}
  function closeDialog(dialog){dialog.close();if(returnFocus&&returnFocus.focus)returnFocus.focus();}
  function sourceRow(label, href, stamp){return `<div class="source-link">${url(href)?`<a href="${esc(url(href))}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`:`<span>${esc(label)}</span>`}<small>${esc(date(stamp))}</small></div>`;}
  function openDetail(code){
    const f=dataset.funds.find(f=>f.code===code);if(!f)return;
    const r=f.reference,s=referenceState(f),a=f.alipay,av=alipayVerified(f);
    const total=rate(f.fees.total);
    const quota=s.usable&&numeric(r.daily_limit)?`¥${num(r.daily_limit)}`:r.status==='paused'?'暂停记录':'待核验';
    const alipayText=av?(a.status==='paused'?'暂停申购':numeric(a.daily_limit)?`¥${num(a.daily_limit)} / 日`:'开放 · 额度未披露'):'尚无有效核验';
    $('#detail-content').innerHTML=`<div class="dialog-top"><span class="small-label">FUND DETAILS / ${esc(f.benchmark)}</span><button class="icon-button close-dialog" aria-label="关闭">${icon('x')}</button></div><h2 id="detail-title">${esc(f.name)}</h2><div class="detail-code"><span>${esc(f.code)} · 人民币 · ${esc({index:'指数基金',feeder:'ETF联接',fof:'指数FOF'}[f.structure])}</span><button data-copy="${esc(code)}">复制代码 ${icon('copy')}</button></div><div class="detail-grid"><div class="detail-stat"><label>公开参考日限额</label><strong>${quota}</strong><small>${esc(r.source_label)}<br>${esc(s.sub)}</small></div><div class="detail-stat"><label>列示固定年费</label><strong>${total}</strong><small>三项费率合计 / 年<br>不等于实际总费用率</small></div></div><div class="detail-notice"><strong>支付宝渠道：${esc(alipayText)}</strong><br>${esc(av?`核验时间：${time(a.checked_at)}；有效至：${time(a.expires_at)}`:a.note||'未核验。请在支付宝搜索基金代码，以下单页为准。')}</div>${dcaDetails(f)}${returnDetails(f)}<h3>年费拆分</h3><div class="fee-breakdown"><div><span>管理费 / 年</span><strong>${rate(f.fees.management)}</strong></div><div><span>托管费 / 年</span><strong>${rate(f.fees.custody)}</strong></div><div><span>销售服务费 / 年</span><strong>${rate(f.fees.sales)}</strong></div></div><p class="detail-note">${esc(f.fee_note)} ${numeric(f.fees.total)&&!numeric(f.fees.management)?'目前只有公开汇总总费率，未反推拆分值。':''}</p><div class="source-link"><span>一次性申购标准费率（首档）</span><small>${rate(f.fees.subscription_standard)}</small></div><div class="source-link"><span>支付宝实际申购费率</span><small>${rate(f.fees.subscription_alipay)}</small></div><p class="detail-note">申购费可能按金额分档。支付宝优惠及赎回费按交易页与持有期限另查，不使用天天基金折扣替代支付宝价格。</p><h3>数据来源与时间</h3>${sourceRow(r.source_label,r.source_url,r.observed_at)}${sourceRow(f.fees.source_label,f.fees.source_url,f.fees.checked_at)}${sourceRow('基金基本资料 / 跟踪标的',f.profile_url,null)}${av?sourceRow('支付宝核验证据',a.evidence_url,a.checked_at):''}<p class="detail-note">${esc(r.note)} 份额之间、渠道之间的限额是否合并：${esc(f.quota_group||'未核实，不进行额度求和。')}</p><div class="detail-actions"><button class="primary-button" data-copy="${esc(code)}">复制代码，到支付宝核验</button><button class="outline-button close-dialog">返回基金列表</button></div>`;
    showDialog($('#detail-dialog'));
  }
  const methodContent=()=>`<h2 id="info-title">数据说明与收录边界</h2><section><h3>01 / 只收录两个标准指数</h3><p>人工白名单收录标准 S&P 500 与 Nasdaq-100 的人民币场外份额，包括普通指数基金、ETF联接和以标准指数为目标的FOF。排除等权重、增强、行业主题、杠杆反向、美元份额及直接在交易所买卖的ETF。首版为 ${dataset.funds.length} 个份额，不承诺穷尽全部产品。新品种需审核后才进入白名单。</p></section><section><h3>02 / 公开参考与支付宝必须分开</h3><p>天天基金公开页只能证明该来源展示的状态；第三方汇总也不等于支付宝下单验证。支付宝核验必须有具体渠道、时间、有效期和证据。缺少任何一项，均标为“待核验”。初版没有支付宝实时交易接口，也没有自动下单功能。</p><p>首版部分暂停状态来自前次查询记录，已明确标为“历史状态待复核”；不能视作今天对支付宝的确认。A/C/D/I类或不同销售机构可能共用限额，未经公告核实不相加。</p></section><section><h3>03 / 年费不是全部成本</h3><p>列示固定年费 = 管理费率 + 托管费率 + 销售服务费率。无法核对拆分时只展示汇总值并标明来源；缺失费率不按零处理。申购、赎回、交易税费及其他运作费用不在此合计内。</p><p>ETF联接的目标ETF费用与管理费、托管费豁免应按合同判断；FOF底层费用也可能影响实际成本。不能把列示合计当成穿透总费率，也不机械双加目标ETF费用。计算器假设全年资产金额不变，只帮助理解固定费率量级。</p></section><section><h3>04 / 每日更新与失败处理</h3><p>项目包含每日北京时间 <strong>08:17、14:17</strong> 两次采集及静态站点发布工作流。当前状态：<strong>${dataset.meta.schedule_active?"每日自动检查已启用，执行结果见更新记录":"定时流程待首次运行确认；当前快照见更新记录"}</strong>。打开网页或点击按钮不会自行启动服务器定时任务。</p><p>公开额度超过36小时未核验，标为待更新；失败不刷新原核验时间。暂停状态优先于来源残留的旧数字。支付宝记录超过36小时必须重新核验；授权来源未配置时，仍只更新公开参考列。费率超过90天未核对会提示复核。</p></section><section><h3>05 / 来源</h3><p><a href="https://www.cifm.com/fund/017641/" target="_blank" rel="noopener noreferrer">摩根基金官方产品页 ↗</a><br><a href="https://fundf10.eastmoney.com/jjfl_019172.html" target="_blank" rel="noopener noreferrer">天天基金公开费率与交易状态页 ↗</a><br><a href="https://qdii.qinguanghui.com/" target="_blank" rel="noopener noreferrer">初版公开汇总快照 ↗</a></p><p>每个份额详情另列对应来源。本站独立制作，未获上述平台背书，不接收账户密码、Cookie、支付凭据或交易指令。</p></section>`;
  function openInfo(type){
    let html;
    if(type==='method')html=methodContent();
    else if(type==='returns')html=`<h2 id="info-title">收益率口径</h2><section><h3>1—5 年：区间累计收益</h3><p>每个份额以其最新已披露净值日为终点，向前回溯对应日历年数。起点取目标日期当日或之前最近一次净值，最多回退14天；2月29日回溯到非闰年时取2月28日。这是区间累计收益率，不是年化收益率，也不是定投收益率。</p></section><section><h3>全部：可获取的完整历史</h3><p>从该人民币份额最早可得净值日起算，未必等于基金法律成立日。A/C等份额各用自己的净值历史，历史不足1—5年时显示“历史不足”。不同份额的“全部”区间长度可能不同，请同时查看详情中的起止日期。</p></section><section><h3>计算与来源</h3><p>依据天天基金公开单位净值历史计算，现金分红按除息日净值再投资，逐期连乘得到区间收益；不以累计净值直接相除。未识别的份额变动或缺失历史不生成收益值。净值已反映基金层面计提的费用，不包含个人申购、赎回等交易费用。</p><p>各行标注净值截止日期，详情提供来源。当前为已采集历史快照，切换年份不会实时获取净值。不同份额截止日可能不同；收益升降不代表未来表现。</p></section>`;
    else if(type==='dca')html=`<h2 id="info-title">每日100元模拟定投口径</h2><section><h3>窗口随当前日期滚动</h3><p>每次每日更新，以北京时间当天为统一基准，分别向前回溯1、2、3个日历年，不使用固定起始日，也不以滞后的最新净值日回推窗口。包含起止日；2月29日回溯到非闰年取2月28日。全部从该份额最早可得净值日起算。区间历史不足时显示“历史不足”。</p></section><section><h3>何时投入与估值</h3><p>周一至周五且有有效净值的日期投入100元，按当日净值买入；无净值日期跳过，不累积补投，周末调休也不投入。仅有净值不代表当日实际开放申购；暂停及限购不纳入本模拟。估值截至最新已披露净值日，尚未披露净值的日期不虚构投入。详情分别展示窗口、投入日期和估值日期。</p></section><section><h3>累计收益与费用</h3><p>现金分红按除息日净值再投资，新增投入从买入之后参与收益。累计盈亏为估算市值减累计投入；累计收益率为累计盈亏除以累计投入，不是年化收益率或内部收益率。基金净值已反映基金层面计提费用，模拟不计个人申购、赎回费用。</p><p>采集失败保留旧结果及原窗口基准日期，并标注更新失败或待更新。切换区间只读取已发布快照，不会发起交易。</p></section>`;
    else if(type==='history')html=`<h2 id="info-title">更新记录</h2><section><p>采集状态：${esc(health.status==='not_deployed'?'尚未部署':health.status)}<br>最近尝试：${esc(time(health.last_attempt_at))}<br>最近整批成功：${esc(time(health.last_success_at))}</p><p>${esc(health.message||'')}</p></section><section>${history.length?history.slice(0,30).map(h=>`<article class="history-item"><time>${esc(time(h.date))}</time><h3>${esc(h.title)}</h3><p>${esc(h.description)}</p></article>`).join(''):'<p>尚无真实更新记录。</p>'}</section><section><p>工作流部署后才会产生真实变更记录。没有新增数据时，不生成虚构“恢复申购”或“额度提高”事件。</p><button class="outline-button" id="reload-snapshot" style="margin-top:14px">重新读取已发布快照</button></section>`;
    else html=`<h2 id="info-title">指数观察 · v0.1</h2><section><h3>一个可修改的公开基金看板</h3><p>首版包含两个指数、${dataset.funds.length}个人民币份额，以及查询、筛选、排序、来源详情、CSV导出、固定费率计算、手机布局与深色模式。此页面既可单文件离线查看，也可部署为静态网站。</p></section><section><h3>当前未完成的接入</h3><p>当前发布版本包含每日北京时间08:17、14:17的自动检查。${dataset.meta.schedule_active?"自动更新已启用，最近执行结果见数据更新卡片。":"定时流程待首次运行确认，当前展示注明日期的快照。"}支付宝授权数据源尚未接入；支付宝额度保持待核验。本站不提供收益保证、基金排名建议或自动交易。</p></section>`;
    $('#info-content').innerHTML=html;showDialog($('#info-dialog'));
  }
  function exportCSV(){
    const rows=getRows();
    const headers=['代码','基金名称','指数','份额','公开参考状态','参考日限额_元','参考来源','参考核验日期','固定年费_%','管理费_%','托管费_%','销售服务费_%','费率核验日期','支付宝状态','支付宝日限额_元','支付宝核验日期','是否历史记录','来源链接',`${RETURN_LABELS[state.period]}累计收益率_%`,'收益起始日期','收益截止日期','收益数据来源',`${DCA_LABELS[state.dcaPeriod]}每日100元模拟定投收益率_%`,'定投累计盈亏_元','定投累计投入_元','定投估算市值_元','定投次数','定投窗口基准日','定投窗口起始日','定投窗口结束日','定投首次投入日','定投最后投入日','定投估值日','定投缺失或更新说明'];
    const csvCell=v=>{let s=String(v??'');if(!numeric(v)&&/^[=+\-@\t\r]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';};
    const body=rows.map(f=>[f.code,f.name,f.benchmark,f.share_class,referenceState(f).label,referenceState(f).usable?f.reference.daily_limit:null,f.reference.source_label,f.reference.observed_at,f.fees.total,f.fees.management,f.fees.custody,f.fees.sales,f.fees.checked_at,alipayVerified(f)?f.alipay.status:'未核验',alipayVerified(f)?f.alipay.daily_limit:null,f.alipay.checked_at,f.reference.verification==='historical'?'是':'否',f.reference.source_url,periodReturn(f).value,periodReturn(f).start_date,periodReturn(f).end_date,returnRecord(f).source_url,dcaPeriod(f).value,dcaPeriod(f).profit,dcaPeriod(f).invested,dcaPeriod(f).market_value,dcaPeriod(f).contribution_count,dcaRecord(f).basis_date,dcaPeriod(f).requested_start,dcaPeriod(f).requested_end,dcaPeriod(f).first_contribution,dcaPeriod(f).last_contribution,dcaPeriod(f).valuation_date,dcaPeriod(f).reason||returnRecord(f).error||(dcaRecord(f).basis_date!==shanghaiToday()?'窗口基准待更新':'')]);
    const blob=new Blob(['\ufeff'+[headers,...body].map(r=>r.map(csvCell).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'});
    const a=document.createElement('a'),link=URL.createObjectURL(blob);a.href=link;a.download=`指数观察_${dataset.meta.snapshot_date}.csv`;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(link),1000);toast(`已导出当前筛选的 ${rows.length} 个份额`);
  }
  async function loadPublished(manual=false){
    if(location.protocol==='file:'){if(manual)toast('离线预览使用内置快照；每日更新需部署后运行');return;}
    try{
      const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);
      let values;
      try{values=await Promise.all(['funds','health','history','returns'].map(async key=>{const res=await fetch(`data/${key}.json`,{cache:'no-store',signal:controller.signal});if(!res.ok)throw new Error('snapshot unavailable');return res.json();}).map((promise,i)=>i===3?promise.catch(()=>null):promise));}finally{clearTimeout(timer);}
      if(!values[0]?.meta || !Array.isArray(values[0]?.funds)||!Array.isArray(values[2])||!values[0].funds.length)throw new Error('invalid snapshot');
      dataset=values[0];health=values[1];history=values[2];if(values[3]?.meta?.schema_version===1&&values[3]?.funds&&!Array.isArray(values[3].funds))returnsData=values[3];renderOverview();renderTable();renderCalculator();
      if(manual){closeDialog($('#info-dialog'));toast('已读取已发布快照；没有触发后台采集');}
    }catch{if(manual)toast('读取失败，保留原快照与原核验日期');}
  }
  document.addEventListener('click',e=>{
    const b=e.target.closest('button');if(!b)return;
    if(b.dataset.copy){copyCode(b.dataset.copy);return;}
    if(b.dataset.detail){openDetail(b.dataset.detail);return;}
    if(b.dataset.modal){openInfo(b.dataset.modal);return;}
    if(b.classList.contains('close-dialog')){closeDialog(b.closest('dialog'));return;}
    if(b.dataset.tab){update({index:b.dataset.tab});return;}
    if(b.dataset.index){update({index:b.dataset.index});$('#funds').scrollIntoView({behavior:'smooth',block:'start'});return;}
    if(b.dataset.status){update({status:b.dataset.status});return;}
    if(b.id==='reload-snapshot')loadPublished(true);
  });
  $$('#detail-dialog,#info-dialog').forEach(d=>{d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)closeDialog(d);}});});
  $('#search').addEventListener('input',e=>update({query:e.target.value}));
  $('#class-filter').addEventListener('change',e=>update({cls:e.target.value}));
  $('#sort-select').addEventListener('change',e=>update({sort:e.target.value}));
  $('#dca-period').addEventListener('change',e=>update({dcaPeriod:e.target.value}));
  $('#sort-dca').addEventListener('click',()=>{const sort=state.sort==='dca-desc'?'dca-asc':'dca-desc';$('#sort-select').value=sort;update({sort});});
  $('#return-period').addEventListener('change',e=>update({period:e.target.value}));
  $('#sort-return').addEventListener('click',()=>{const sort=state.sort==='return-desc'?'return-asc':'return-desc';$('#sort-select').value=sort;update({sort});});
  $('#verified-only').addEventListener('change',e=>update({verified:e.target.checked}));
  $('#prev-page').addEventListener('click',()=>{state.page--;renderTable();});$('#next-page').addEventListener('click',()=>{state.page++;renderTable();});
  $('#sort-fee').addEventListener('click',()=>{state.sort=state.sort==='fee-asc'?'fee-desc':'fee-asc';$('#sort-select').value=state.sort;state.page=1;renderTable();});
  $('#sort-limit').addEventListener('click',()=>{update({sort:'limit-desc'});$('#sort-select').value='limit-desc';});
  $('#reset-button').addEventListener('click',()=>{state={index:'all',status:'all',cls:'all',query:'',sort:'smart',verified:false,page:1,period:'1y',dcaPeriod:'1y'};$('#dca-period').value='1y';$('#return-period').value='1y';$('#search').value='';$('#class-filter').value='all';$('#sort-select').value='smart';$('#verified-only').checked=false;renderTable();});
  $('#export-button').addEventListener('click',exportCSV);$('#principal').addEventListener('input',calculate);$('#calc-fund').addEventListener('change',calculate);
  const setTheme=theme=>{document.documentElement.dataset.theme=theme;$('#theme-toggle').innerHTML=icon(theme==='dark'?'sun':'moon');$('#theme-toggle').setAttribute('aria-label',theme==='dark'?'切换浅色模式':'切换深色模式');};
  let saved;try{saved=localStorage.getItem('index-watch-theme');}catch{}
  setTheme(saved==='dark'?'dark':'light');
  $('#theme-toggle').addEventListener('click',()=>{const theme=document.documentElement.dataset.theme==='dark'?'light':'dark';setTheme(theme);try{localStorage.setItem('index-watch-theme',theme);}catch{}});
  document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)&&!document.querySelector('dialog[open]')){e.preventDefault();$('#search').focus();}});
  icons();renderOverview();renderTable();renderCalculator();loadPublished();
})();
