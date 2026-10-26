/* DOM integration checks without a browser. Optional dependency: linkedom. */
const {parseHTML}=require('linkedom');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');

const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'site/index.html'),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const bootData=JSON.parse(html.match(/<script id="seed-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
let checks=0;
function check(value,label){assert.ok(value,label);checks++;}

function createApp({online=false,missingReturns=false,seed=bootData}={}){
  const {window}=parseHTML(html),document=window.document;
  document.querySelector('#seed-data').textContent=JSON.stringify(seed);
  // linkedom supplies DOM semantics; patch only unimplemented native controls.
  Object.defineProperty(window.HTMLSelectElement.prototype,'value',{
    configurable:true,
    get(){const o=[...this.querySelectorAll('option')];return (o.find(x=>x.hasAttribute('selected'))||o[0])?.getAttribute('value')||'';},
    set(v){for(const o of this.querySelectorAll('option'))o.toggleAttribute('selected',o.getAttribute('value')===v);}
  });
  window.location={protocol:online?'https:':'file:'};
  window.localStorage={getItem(){return null},setItem(){}};
  window.setTimeout=()=>0;window.clearTimeout=()=>{};
  window.Blob=Blob;window.AbortController=AbortController;
  let download;
  window.URL=class extends URL{static createObjectURL(blob){download=blob;return 'blob:test';}static revokeObjectURL(){}};
  window.HTMLElement.prototype.showModal=function(){this.setAttribute('open','');};
  window.HTMLElement.prototype.close=function(){this.removeAttribute('open');};
  window.fetch=async href=>{
    const key=href.match(/data\/(\w+)\.json/)[1];
    if(key==='returns'&&missingReturns)throw Error('offline');
    return {ok:true,json:async()=>({funds:bootData.dataset,health:bootData.health,history:bootData.history,returns:bootData.returns})[key]};
  };
  vm.runInContext(script,vm.createContext(window));
  const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
  const click=s=>$(s).dispatchEvent(new window.Event('click',{bubbles:true}));
  const change=(s,value)=>{$(s).value=value;$(s).dispatchEvent(new window.Event('change',{bubbles:true}));};
  const search=value=>{$('#search').value=value;$('#search').dispatchEvent(new window.Event('input',{bubbles:true}));};
  return {$,$$,click,change,search,download:()=>download};
}

(async()=>{
  const app=createApp(),{$,$$,change,click,search}=app;
  check($$('#fund-rows tr').length===10,'Initial page still has ten funds');
  check($$('#fund-rows tr:first-child td').length===8,'New column renders without losing original columns');
  check($('#return-period').value==='1y'&&$('#return-heading-label').textContent==='近1年收益率','One year is default');
  check($$('#return-period option').length===6,'All six periods are selectable');
  for(const period of ['1y','2y','3y','4y','5y','all']){
    change('#return-period',period);
    const first=$('#fund-rows tr'),code=first.getAttribute('data-row');
    const item=bootData.returns.funds[code].periods[period];
    const expected=item.value===null?'—':`${item.value>0?'+':''}${item.value.toFixed(2)}%`;
    check(first.querySelector('.return-cell').textContent.includes(expected),`Correct ${period} return after switching`);
  }
  change('#return-period','5y');
  search('017641');
  check($('.return-cell').textContent.includes('历史不足')&&!$('.return-cell').textContent.includes('0.00%'),'Young fund is missing, never zero or since inception');
  search('');click('#sort-return');
  let values=$$('#fund-rows tr').map(row=>bootData.returns.funds[row.getAttribute('data-row')].periods['5y'].value);
  check(values.every((v,i)=>v!==null&&(!i||v<=values[i-1])),'Descending selected-period sort');
  click('#sort-return');
  values=$$('#fund-rows tr').map(row=>bootData.returns.funds[row.getAttribute('data-row')].periods['5y'].value);
  check(values.every((v,i)=>v!==null&&(!i||v>=values[i-1])),'Ascending sort keeps missing returns last');
  check($('.return-heading').getAttribute('aria-sort')==='ascending','Sort direction is accessible');
  click('.return-value');
  check($('#detail-dialog').hasAttribute('open')&&$$('.return-detail-grid>div').length===6,'Details show all six periods');
  check($('#detail-content').textContent.includes('非年化')&&$('#detail-content').textContent.includes('天天基金公开净值历史'),'Details retain method and source');
  click('#detail-dialog .close-dialog');
  click('[data-modal="returns"]');
  check($('#info-dialog').textContent.includes('累计净值直接相除'),'Returns methodology opens');
  click('#info-dialog .close-dialog');
  change('#return-period','4y');click('#export-button');
  const csv=await app.download().text();
  check(csv.includes('近4年累计收益率_%')&&csv.includes('收益截止日期'),'CSV matches selected period and dates');
  search('017641');click('#reset-button');
  check($('#return-period').value==='1y'&&$$('#fund-rows tr').length===10,'Reset also resets period');
  search('000000');check(!$('#empty-state').hidden,'Existing empty search state still works');
  const online=createApp({online:true,missingReturns:true});
  await new Promise(resolve=>setImmediate(resolve));
  check(online.$$('.return-value').length>0&&online.$$('#fund-rows tr').length===10,'Returns fetch failure retains embedded snapshot and original board');
  const empty=structuredClone(bootData);delete empty.returns;
  const older=createApp({seed:empty});
  check(older.$('.return-cell').textContent.includes('暂无数据'),'Older snapshots without returns remain compatible');
  const zero=structuredClone(bootData);for(const f of Object.values(zero.returns.funds))f.periods['1y'].value=0;
  const zeroApp=createApp({seed:zero});
  check(zeroApp.$('.return-value').textContent==='0.00%','Actual zero return is displayed as zero');
  const dca=createApp();
  check(dca.$$('#dca-period option').length===4&&dca.$('#dca-period').value==='1y','Four independent DCA windows default to one year');
  for(const period of ['1y','2y','3y','all']){
    dca.change('#dca-period',period);
    const row=dca.$('#fund-rows tr'),record=bootData.returns.funds[row.getAttribute('data-row')];
    const item=record.dca.periods[period];
    const expected=item.value===null?'—':`${item.value>0?'+':''}${item.value.toFixed(2)}%`;
    check(row.querySelector('.dca-cell').textContent.includes(expected),`DCA ${period} displays correct value`);
    check(dca.$('#return-period').value==='1y','Changing DCA leaves the lump-sum period intact');
  }
  dca.change('#dca-period','3y');dca.click('#sort-dca');
  let dcaValues=dca.$$('#fund-rows tr').map(row=>bootData.returns.funds[row.getAttribute('data-row')].dca.periods['3y'].value);
  check(dcaValues.every((v,i)=>v!==null&&(!i||v<=dcaValues[i-1])),'Descending DCA sort uses selected period');
  dca.click('#sort-dca');
  dcaValues=dca.$$('#fund-rows tr').map(row=>bootData.returns.funds[row.getAttribute('data-row')].dca.periods['3y'].value);
  check(dcaValues.every((v,i)=>v!==null&&(!i||v>=dcaValues[i-1])),'Ascending DCA sort keeps unknown values last');
  check(dca.$('.dca-heading').getAttribute('aria-sort')==='ascending','DCA sort direction is accessible');
  dca.click('.dca-value');
  check(dca.$$('.dca-detail-grid>div').length===4,'DCA detail includes four windows');
  for(const label of ['窗口基准','累计投入','估算市值','投入次数','净值估值','历史模拟'])check(dca.$('#detail-content').textContent.includes(label),`DCA detail contains ${label}`);
  dca.click('#detail-dialog .close-dialog');
  dca.click('#export-button');const dcaCsv=await dca.download().text();
  check(dcaCsv.includes('近3年每日100元模拟定投收益率_%')&&dcaCsv.includes('定投窗口基准日')&&dcaCsv.includes('定投累计盈亏_元'),'CSV exports DCA amount, dates and selected window');
  dca.click('[data-modal="dca"]');check(dca.$('#info-dialog').textContent.includes('不使用固定起始日'),'DCA method explains rolling calendar windows');dca.click('#info-dialog .close-dialog');
  dca.search('017641');dca.click('#reset-button');check(dca.$('#dca-period').value==='1y','Reset restores DCA period');
  check(online.$('.dca-value')!==null,'Network failure retains embedded DCA snapshot');
  check(older.$('.dca-cell').textContent.includes('暂无定投数据'),'Old snapshots without DCA remain usable');
  const staleSeed=structuredClone(bootData);
  for(const record of Object.values(staleSeed.returns.funds))record.dca.basis_date='2000-01-01';
  const stale=createApp({seed:staleSeed});check(stale.$('.dca-cell').textContent.includes('待更新 · 基准 2000-01-01'),'Outdated window is labelled with original basis, never relabelled today');
  const failedSeed=structuredClone(bootData);
  for(const record of Object.values(failedSeed.returns.funds))record.error='采集失败';
  const failed=createApp({seed:failedSeed});check(failed.$('.dca-cell').textContent.includes('更新失败'),'Failed refresh remains visible in DCA column');
  const dcaZero=structuredClone(bootData);
  for(const record of Object.values(dcaZero.returns.funds))record.dca.periods['1y'].value=0;
  check(createApp({seed:dcaZero}).$('.dca-value').textContent==='0.00%','Zero DCA return is not missing');
  const mobileCss=fs.readFileSync(path.join(root,'site/assets/style.css'),'utf8');
  check(mobileCss.includes('@media(max-width:700px)')&&mobileCss.includes('.dca-heading,.dca-cell{min-width:0}'),'DCA column has mobile card width rules');
  console.log(JSON.stringify({dom_checks:checks,status:'passed',browser_layout:'not verified'},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
