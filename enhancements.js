/* Fieldnotes 2.0 interface enhancements. All article data comes from data/latest.json. */
(function () {
'use strict';
const HOME_TASKS = {
 winter: [
 ['Check water around the foundation','Inspect basement damp spots, gutter discharge, grading and splash blocks after rain or snowmelt.','https://extension.missouri.edu/'],
 ['Winterize outdoor water connections','Remove hoses, locate exterior shutoffs and check exposed pipes at the home or outbuildings.','https://www.familyhandyman.com/'],
 ['Survey your two-acre tree line','Map storm-damaged branches, areas of standing water and trees over structures for follow-up.','https://extension.missouri.edu/'],
 ['Map weak outdoor Wi-Fi zones','Check coverage near your yard and outbuildings before selecting a weather-rated wired access point.','https://www.wi-fi.org/']
 ],
 spring: [
 ['Inspect deck and rail fasteners','Check loose railings, flashing, soft wood and drainage before summer use.','https://www.thisoldhouse.com/'],
 ['Plan erosion and drainage improvements','Observe runoff during heavy rain and assess soil cover, swales and grading patterns.','https://extension.missouri.edu/'],
 ['Prepare equipment for two acres','Service mower blades, belts and filters and organize yard equipment.','https://www.familyhandyman.com/'],
 ['Plan native landscaping and pollinator strips','Choose planting areas by sunlight, soil moisture and mowing needs.','https://extension.missouri.edu/']
 ],
 summer: [
 ['Check gutters and downspouts after storms','Look for damage and ensure water discharges away from basement walls.','https://www.thisoldhouse.com/'],
 ['Compare water flow at distant faucets','Track household supply pressure and delivery with multiple fixtures running.','https://www.familyhandyman.com/'],
 ['Manage low-use acreage','Consider native cover and reduced mowing in suitable low-traffic areas.','https://extension.missouri.edu/'],
 ['Keep basement humidity in check','Inspect condensate drainage, moisture entry and HVAC filter condition.','https://www.energy.gov/energysaver']
 ],
 fall: [
 ['Clear gutters before freezing weather','Check discharge routes, underground drains and foundation grading.','https://www.familyhandyman.com/'],
 ['Inspect the deck for winter damage risks','Document loose boards, weathered finish, rail attachment and soft spots.','https://www.thisoldhouse.com/'],
 ['Protect hoses, faucets and unheated lines','Drain hoses and identify pipes that might freeze in outbuildings.','https://www.thisoldhouse.com/'],
 ['Map acreage maintenance zones','Mark trees, drainage paths, structures and spots that need spring repair.','https://extension.missouri.edu/']
 ]
};
let feedInfo={source_count:0,feed_count:0,feed_health:[]};
let liveRefreshRunning=false;
const safeText = x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const urlOk = u=>typeof u==='string'&&/^https:\/\//i.test(u);
function makeSection(id,title,description,gridClass,gridId){
 const sec=document.createElement('section');sec.className='section';sec.id=id;
 sec.innerHTML='<div class="section-header"><h2>'+safeText(title)+'</h2><span class="tag">Curated for you</span></div>'+
 '<p class="intro">'+safeText(description)+'</p><div class="'+gridClass+'" id="'+gridId+'"></div>';
 return sec;
}
function fillHome(){
 const root=document.getElementById('homeProjects');if(!root)return;
 const data=HOME_TASKS[season(new Date())]||HOME_TASKS.winter;root.replaceChildren();
 for(const [title,desc,url] of data){
  const box=document.createElement('div');box.className='project';
  box.innerHTML='<b>'+safeText(title)+'</b><p>'+safeText(desc)+'</p>'+
   '<a href="'+safeText(url)+'" target="_blank" rel="noopener noreferrer">Project tips ↗</a>';
  root.append(box);
 }
}
function fillComics(){
 const root=document.getElementById('comicsGrid');if(!root)return;
 const items=STORIES.filter(s=>s.catKey==='comics').sort((a,b)=>String(b.date).localeCompare(String(a.date))).slice(0,4);
 root.replaceChildren();
 if(!items.length){
  root.innerHTML='<div class="comic-item"><h3>Visit the creators</h3><p>The comics feed did not return a recent strip.</p><a href="https://xkcd.com/" target="_blank" rel="noopener noreferrer">xkcd ↗</a> · <a href="https://poorlydrawnlines.com/" target="_blank" rel="noopener noreferrer">Poorly Drawn Lines ↗</a></div>';
  return;
 }
 for(const item of items){
  if(!urlOk(item.url))continue;
  const box=document.createElement('article');box.className='comic-item';
  const img=urlOk(item.image)?'<a href="'+safeText(item.url)+'" target="_blank" rel="noopener noreferrer"><img src="'+safeText(item.image)+'" loading="lazy" referrerpolicy="no-referrer" alt="'+safeText(item.headline)+'"></a>':'';
  box.innerHTML='<h3>'+safeText(item.headline)+'</h3><div class="meta">'+safeText(item.source)+' · '+safeText(formatDate(item.date))+'</div>'+img+
    '<a href="'+safeText(item.url)+'" target="_blank" rel="noopener noreferrer">Read comic at source ↗</a>';
  root.append(box);
 }
}
function renderV2(){
 const q=document.getElementById('search').value.trim().toLowerCase();
 const list=STORIES.filter(x=>(selected==='all'?x.catKey!=='comics':x.catKey===selected)
  &&(!showSaved||saved.has(x.id))
  &&(!q||[x.headline,x.source,x.summary,x.why,x.category,x.tag].some(v=>String(v??'').toLowerCase().includes(q))));
 list.sort((a,b)=>sortMode==='latest'?(String(b.date).localeCompare(String(a.date))||(b.score||0)-(a.score||0)):
   sortMode==='oldest'?(String(a.date).localeCompare(String(b.date))||(b.score||0)-(a.score||0)):
   ((b.score||0)-(a.score||0)||String(b.date).localeCompare(String(a.date))));
 const cards=document.getElementById('cards');cards.replaceChildren();
 document.getElementById('storyTitle').textContent=showSaved?'Saved stories':
  (selected==='all'?'Most relevant stories for you':CATS.find(c=>c[1]===selected)?.[0]||'Stories');
 document.getElementById('storyCount').textContent=list.length+' stories';
 if(!list.length){cards.innerHTML='<div class="empty">No stories match this filter. Try another topic.</div>';}
 for(const item of list){
  const src=urlOk(item.url)?item.url:'https://news.google.com/';
  const savedItem=saved.has(item.id);
  const article=document.createElement('article');article.className='story';
  const image=urlOk(item.image)?'<a href="'+safeText(src)+'" target="_blank" rel="noopener noreferrer"><img class="article-image" src="'+safeText(item.image)+'" loading="lazy" referrerpolicy="no-referrer" alt="'+safeText(item.headline)+'"></a>':'';
  const pct=Number(item.confidence_pct);
  const confidence=item.confidence_pct!=null&&Number.isFinite(pct)?
    '<div class="evidence-row"><span class="evidence-score" title="'+safeText(item.confidence_basis||'Automated corroboration, not a truth probability')+'">'+
    'Evidence support '+Math.round(pct)+'%</span></div>':'';
  const supporting=Array.isArray(item.corroboration)?item.corroboration.filter(c=>urlOk(c.url)).slice(0,4):[];
  const comparisons=supporting.length?
    '<div class="reporting-links"><strong>Compare reporting &amp; viewpoints</strong>'+
     supporting.map(c=>'<a href="'+safeText(c.url)+'" target="_blank" rel="noopener noreferrer">'+safeText(c.source)+' ↗</a>').join('')+
     '<div>Sources report on apparently similar events; differences in framing or conclusions should be checked in full articles.</div></div>':
    '<div class="reporting-links">One feed publisher; independent corroboration not identified.</div>';
  article.innerHTML='<div class="story-top"><div><span class="pill">'+safeText(item.category||'News')+'</span>'+
   '<div class="meta">'+safeText(item.source||'Publisher')+' · '+safeText(formatDate(item.date))+' · '+safeText(item.kind||'News')+'</div></div>'+
   '<button class="save '+(savedItem?'active':'')+'" type="button" aria-label="'+(savedItem?'Remove bookmark':'Save story')+'">'+(savedItem?'★':'☆')+'</button></div>'+
   image+'<h3>'+safeText(item.headline)+'</h3><p>'+safeText(item.summary)+'</p>'+confidence+
   '<div class="why"><strong>Why it matters to you</strong>'+safeText(item.why)+'</div>'+comparisons+
   '<div class="story-bottom"><small>'+safeText(item.note||item.tag||'Publisher RSS')+'</small>'+
   '<a href="'+safeText(src)+'" target="_blank" rel="noopener noreferrer">Read source ↗</a></div>';
  article.querySelector('.save').onclick=()=>{
   saved.has(item.id)?saved.delete(item.id):saved.add(item.id);
   saveBookmarks();renderV2();document.getElementById('savedCount').textContent=saved.size;
  };
  cards.append(article);
 }
 fillComics();
}
function statusV2(){
 const date=toDate(edition),age=date?(Date.now()-date.getTime())/86400000:999;
 const badge=document.getElementById('statusBadge');
 badge.className='badge'+(age>2||feedMode==='curated_snapshot'?' warn':'');
 badge.textContent=feedMode==='curated_snapshot'?'Starter snapshot':age>2?'Feed may be stale':'Recently refreshed';
 const stamp=date?new Intl.DateTimeFormat('en-US',{timeZone:'America/Chicago',weekday:'short',month:'short',day:'numeric',year:'numeric',hour:'numeric',minute:'2-digit',hour12:true,timeZoneName:'short'}).format(date):'Unavailable';
 document.getElementById('updateLabel').textContent='Last refreshed: '+stamp+(feedMode==='curated_snapshot'?' · starter edition':'');
 document.getElementById('todayLabel').textContent=new Date().toLocaleDateString('en-US',{timeZone:'America/Chicago',weekday:'long',month:'long',day:'numeric',year:'numeric'})+' · Missouri edition';
 const health=document.getElementById('feedHealth');
 if(health){
  const failed=(feedInfo.feed_health||[]).filter(x=>x.status==='failed');
  const quiet=(feedInfo.feed_health||[]).filter(x=>x.status==='no_matching_recent_articles');
  health.innerHTML='<strong>'+safeText(feedInfo.source_count)+' of '+safeText(feedInfo.feed_count)+' publisher feeds reachable</strong> · '+failed.length+
   ' failures · '+quiet.length+' without recent matching articles.'+(failed.length?
   '<details><summary>Feeds to revisit</summary><p>'+failed.map(x=>safeText(x.source)).join(', ')+'</p></details>':'');
 }
}
async function enhancedRefresh(){
 if(liveRefreshRunning||location.protocol==='file:')return;
 liveRefreshRunning=true;
 const btn=document.getElementById('refreshBtn');btn.disabled=true;btn.textContent='↻ Checking…';
 try{
  const response=await fetch('./data/latest.json?cb='+Date.now(),{cache:'no-store'});
  if(!response.ok)throw Error('HTTP '+response.status);
  const data=await response.json();
  if(!Array.isArray(data.stories)||!data.stories.length)throw Error('Empty news feed');
  STORIES=data.stories.filter(x=>x&&x.headline&&urlOk(x.url));
  edition=data.updated_at||edition;feedMode=data.mode||'rss';
  feedInfo={source_count:data.source_count||0,feed_count:data.feed_count||0,feed_health:data.feed_health||[]};
  render();
 }catch(err){
  console.warn('Fieldnotes refresh failed:',err);
  const msg=document.getElementById('updateLabel');msg.textContent='Live refresh unavailable · showing last saved edition';
 }finally{btn.disabled=false;btn.textContent='↻ Check updates';liveRefreshRunning=false;}
}
function init(){
 if(typeof CATS==='undefined'||typeof render!=='function'){console.warn('Fieldnotes base interface missing');return;}
 if(!CATS.some(x=>x[1]==='property'))CATS.push(['Home & 2 Acres','property','⌂']);
 if(!CATS.some(x=>x[1]==='comics'))CATS.push(['Comics','comics','☻']);
 const cards=document.getElementById('cards');
 const newsSection=cards.closest('section');
 const weekend=document.getElementById('weekendSection');
 if(newsSection&&weekend){
  const lead=document.querySelector('.hero');
  if(lead){
   const note=document.createElement('div');note.className='evidence-note';
   note.innerHTML='<strong>Evidence scores ≠ probability of truth.</strong> A percentage indicates how many independent publisher headlines closely corroborate a story. Single-feed reporting is not independently confirmed here. For disputed stories, compare source links and framing.';
   lead.after(note);
  }
  const home=makeSection('propertySection','🏡 Home & Two-Acre Property',
   'Seasonal tips for your deck, basement, drainage, yard, outdoor networking, trees and land.',
   'project-grid','homeProjects');
  const comics=makeSection('comicsSection','🎨 Comics & a Quick Laugh',
   'Official creator feeds with linked images when supplied; always visit the original strip.',
   'comic-grid','comicsGrid');
  newsSection.after(home,comics,weekend);
  fillHome();
 }
 const right=document.querySelector('.aside.right .panel:last-child');
 if(right&&!document.getElementById('feedHealth')){
  right.insertAdjacentHTML('beforeend','<div id="feedHealth">Checking feed health…</div>');
 }
 renderCards=renderV2;
 updateStatus=statusV2;
 refresh=enhancedRefresh;
 document.getElementById('refreshBtn').onclick=enhancedRefresh;
 render();
 enhancedRefresh();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
