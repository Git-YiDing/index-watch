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
  check($$('#fund-rows tr:first-child td').length===7,'New column renders without losing original columns');
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
  console.log(JSON.stringify({dom_checks:checks,status:'passed',browser_layout:'not verified'},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
