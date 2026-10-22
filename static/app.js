const $ = id => document.getElementById(id);
const labels = {wholesale_price:'Wholesale price',retail_benchmark:'Retail benchmark',shipping_per_unit:'Shipping / unit',duty_per_unit:'Duty / unit',moq:'Minimum order'};
let currentRun;
const node = (tag, text, className) => { const el=document.createElement(tag); if(text!==undefined) el.textContent=text; if(className) el.className=className; return el; };
function link(url, text) { const el=node('a',text); try { const parsed=new URL(url); if(!['http:','https:'].includes(parsed.protocol)) return node('span','Invalid source URL'); el.href=parsed.href; el.target='_blank'; el.rel='noopener noreferrer'; } catch { return node('span','Invalid source URL'); } return el; }
function money(value,currency) {return value===null?'Not available':new Intl.NumberFormat('en',{style:'currency',currency,maximumFractionDigits:2}).format(value);}
function render(data) {
 const r=data.result, demo=data.mode==='offline-demo', fmt=v=>money(v,r.currency);
 $('empty').hidden=true; $('empty').style.display='none'; $('report').hidden=false;
 $('mode').textContent=demo?'OFFLINE DEMO · FICTIONAL DATA · SCRIPTED TOOL CALLS':'LIVE GEMINI RESEARCH · UNVERIFIED CANDIDATE';
 $('title').textContent=r.product_title; $('supplier').textContent=r.supplier_name+' · MOQ '+(r.moq??'unknown');
 $('decision').textContent=r.decision;
 $('caution').textContent=demo?'All supplier names, links and prices here are invented. No AI or network research ran. This demonstrates the tools and calculations.':'Web research is a candidate offer, not a verified quote. Check source pages, pack sizes, tax basis and delivery terms with the supplier. No funds or messages have been sent.';
 $('metrics').replaceChildren();
 for(const [title,value,note] of [['Landed cost / unit',fmt(r.landed_cost),'Excludes recoverable VAT'],['Gross margin',r.gross_margin_percent===null?'Not available':r.gross_margin_percent.toFixed(1)+'%','Target '+(r.target_margin*100).toFixed(1)+'%'],['Break-even units',r.breakeven_units??'Not available','Fixed costs '+fmt(r.fixed_costs)],['MOQ cost',fmt(r.moq_cost),'Landed cost × order minimum']]) {const card=node('div',undefined,'metric');card.append(node('span',title),node('strong',String(value)),node('small',note));$('metrics').append(card);}
 $('currency').textContent=r.currency+' · ONE SELLABLE UNIT'; $('economics').replaceChildren();
 for(const [name,value,total] of [['Retail benchmark · VAT inclusive',r.retail_benchmark],['VAT component · scenario',r.vat_amount],['Net retail revenue',r.net_retail_price,true],['Wholesale',r.wholesale_price],['Shipping',r.shipping_per_unit],['Duty',r.duty_per_unit],['Landed cost',r.landed_cost,true],['Gross profit / unit',r.gross_profit,true]]) {const row=node('div',undefined,'econ-row'+(total?' total':''));row.append(node('span',name),node('span',fmt(value)));$('economics').append(row);}
 $('missing').textContent=r.missing_fields.length?'Unresolved: '+r.missing_fields.map(f=>labels[f]||f).join(', ')+'. The margin decision is blocked.':'Required numeric inputs are populated. Their accuracy and applicability still need human verification.';
 $('notes').textContent=r.notes; $('evidence').replaceChildren();
 for(const item of data.evidence){const tr=node('tr'),source=node('td');source.append(link(item.url,demo?'Fictional example':new URL(item.url).hostname));tr.append(node('td',labels[item.field]||item.field),source,node('td',item.note));$('evidence').append(tr);}
 if(!data.evidence.length){const tr=node('tr'),td=node('td','No field-specific evidence returned.');td.colSpan=3;tr.append(td);$('evidence').append(tr);}
 $('grounding').replaceChildren(); if(data.grounding_sources.length){$('grounding').append(node('strong','Search grounding sources (not independent verification):'));for(const s of data.grounding_sources)$('grounding').append(link(s.url,s.title));}
 $('budget').textContent=data.research_calls+' / 2 RESEARCH CALLS'; $('trace').replaceChildren();
 for(const step of data.trace){const detail=node('details',undefined,'trace-step');detail.append(node('summary',String(step.step).padStart(2,'0')+' · '+step.tool+' · '+step.status),node('pre',JSON.stringify({arguments:step.arguments,result:step.result},null,2)));$('trace').append(detail);}
 $('downloads').replaceChildren();for(const [filename,label] of [['catalog_entry.csv','Catalog CSV'],['supplier_rfq.txt','Inquiry draft'],['investigation.json','Full evidence & trace']]){const a=node('a',label);a.href='/api/runs/'+currentRun+'/'+filename;a.download=filename;$('downloads').append(a);}
 $('status').textContent=(demo?'Offline demonstration complete. ':'Live research complete. ')+data.stop_reason+'.';
}
async function run(demo) {
 if(!$('request').reportValidity())return;
 $('demo').disabled=true;$('live').disabled=true;$('status').className='status';$('report').hidden=true;
 $('status').textContent=demo?'Running the fictional demonstration…':'Investigating one supplier candidate… Live calls can take several minutes. Keep this page open.';
 try {
  const response=await fetch('/api/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({keyword:$('product').value,region:$('region').value,vat_rate:Number($('vat').value)/100,target_margin:Number($('margin').value)/100,fixed_costs:Number($('fixed').value),demo})});
  const body=await response.json();if(!response.ok)throw Error(body.error);currentRun=body.id;
  while(true){await new Promise(resolve=>setTimeout(resolve,800));const poll=await fetch('/api/runs/'+currentRun);const data=await poll.json();if(!poll.ok||data.status==='error')throw Error(data.error);if(data.status==='complete'){render(data);break;}}
 }catch(error){$('status').textContent=error.message;$('status').className='status error';}
 finally{$('demo').disabled=false;await config();}
}
async function config(){try{const c=await (await fetch('/api/config')).json();$('live').disabled=!c.live_available;$('configuration').textContent=c.live_available?'Live mode configured · '+c.model:'Offline demo is ready. For live research, set GEMINI_API_KEY in your terminal before starting the server.';}catch{$('configuration').textContent='Unable to reach the local server.';}}
$('request').addEventListener('submit',e=>{e.preventDefault();run(false);});$('demo').addEventListener('click',()=>run(true));config();
