'use strict';
const $ = s => document.querySelector(s);
const clone = x => JSON.parse(JSON.stringify(x));
let token = new URLSearchParams(location.hash.slice(1)).get('token') || sessionStorage.getItem('orbit-token') || '';
if (token) sessionStorage.setItem('orbit-token', token);
history.replaceState(null, '', location.pathname);
let state, draft, saved, page = 'overview', busy = false;
const pages = [ ['overview','◉','Overview'], ['appearance','◐','Appearance'], ['layout','▦','Layout & cards'], ['personal','◎','Profile & clock'], ['weather','☁','Weather'], ['integrations','♫','Music & system'], ['apps','▤','Applications'], ['links','↗','Links'], ['folders','▱','Places'], ['advanced','⌘','Advanced'], ['maintenance','↺','Backups & health'] ];
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key in node) node[key] = value;
    else node.setAttribute(key, value);
  }
  children.flat().filter(x => x !== null && x !== undefined).forEach(x => node.append(x));
  return node;
}
async function api(route, body) {
  const res = await fetch('/api/' + route, {method:body ? 'POST' : 'GET', headers:{'X-Orbit-Token':token, ...(body ? {'Content-Type':'application/json'} : {})}, body:body ? JSON.stringify(body) : undefined});
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed. Please try again.');
  return data;
}
function message(text, error = false) { $('#message').hidden = !text; $('#message').textContent = text; $('#message').classList.toggle('error', error); }
async function attempt(action) { try { await action(); } catch (error) { message(error.message, true); } }
function get(path) { return path.split('.').reduce((obj,k) => obj[k], draft); }
function put(path, value) { const parts = path.split('.'); const key = parts.pop(); parts.reduce((obj,k) => obj[k], draft)[key] = value; changed(); }
function dirty() { return JSON.stringify(draft) !== JSON.stringify(saved); }
function changed() { $('#save-state').textContent = dirty() ? 'You have unsaved changes' : 'All changes saved'; $('#discard').disabled = !dirty() || busy; $('#save').disabled = busy; preview(); }
function title(kicker, headline, description) { return [el('span',{class:'overline',text:kicker}),el('h1',{text:headline}),el('p',{class:'intro',text:description})]; }
function section(title, description, ...children) { return el('section',{class:'section'},el('h2',{text:title}),description ? el('p',{text:description}) : null,el('div',{class:'fields'},children)); }
function button(text, action, style = '') { return el('button',{type:'button',text,class:style,onclick:() => attempt(action)}); }
function field(path, label, help = '', options = {}) {
  const value = get(path); let input;
  if (options.choices) {
    input = el('select', {onchange:e => put(path, options.numeric ? Number(e.target.value) : e.target.value)}, options.choices.map(x => el('option',{value:Array.isArray(x)?x[0]:x, text:Array.isArray(x)?x[1]:x})));
    input.value = value;
  } else {
    input = el('input', {type:options.type || 'text', value, ...(options.min !== undefined ? {min:options.min,max:options.max,step:options.step || 1} : {}), oninput:e => put(path, ['number','range'].includes(options.type) ? Number(e.target.value) : e.target.value)});
  }
  input.setAttribute('aria-label', label);
  return el('label',{class:'field'},el('span',{text:label}),input,help ? el('small',{text:help}) : null);
}
function toggle(path,label,help='') {
  return el('label',{class:'toggle'},el('span',{class:'copy'},el('span',{text:label}),help ? el('small',{text:help}) : null),el('input',{type:'checkbox',checked:get(path),onchange:e=>put(path,e.target.checked)}));
}
function themes() {
  return el('div',{class:'theme-grid'},Object.entries(state.themes).map(([name,colors])=>{
    const art=el('span',{class:'theme-art'}); art.style.background=colors[0];
    [colors[1],colors[4]].forEach(c=>{const i=el('i');i.style.background=c;art.append(i);});
    return el('button',{class:'theme'+(draft.appearance.preset===name?' chosen':''),type:'button','aria-pressed':draft.appearance.preset===name,onclick:()=>{put('appearance.preset',name);put('appearance.mode',name==='minimal'?'light':'dark');put('appearance.accent','');show();}},art,el('span',{class:'theme-name',text:name}));
  }));
}
function picker(path, label, kind) {
  const controls=el('div',{class:'inline'},button('Browse…', async()=>{const data=await api('choose',{kind});if(data.path){put(path,data.path);show();}}),button('Clear',()=>{put(path,'');show();},'ghost'));
  if(kind==='image') {
    const input=el('input',{type:'file',accept:'image/png,image/jpeg',hidden:true,onchange:e=>attempt(async()=>{
      const file=e.target.files[0];if(!file)return;if(file.size>5*1024*1024)throw new Error('Choose a PNG or JPEG smaller than 5 MB.');
      const image=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=reject;r.readAsDataURL(file);});
      const data=await api('upload',{image});put(path,data.path);show();
    })});
    controls.append(button('Upload image',()=>input.click()),input);
  }
  return el('div',{},field(path,label,'Use a full path, choose a file, or upload an image.'),controls);
}
function overview() {
  return [...title('WELCOME TO YOUR SPACE','Good things start here.','A quieter desktop, shaped around you. Start with a look, choose what matters, and make yourself at home.'),
    el('div',{class:'welcome'},el('span',{class:'overline',text:draft.setup_complete?'YOUR DAILY COMPANION':'LET’S MAKE IT YOURS'}),el('h2',{text:draft.setup_complete?'A workspace that feels like you.':'Three small steps. A whole new space.'}),el('p',{text:'Choose a theme, arrange your cards, and add your city. Everything can be changed later. Save & apply when you’re ready.'}),el('div',{class:'steps'},button('1 · Choose a look',()=>navigate('appearance')),button('2 · Arrange cards',()=>navigate('layout')),button('3 · Add your city',()=>navigate('weather')))),
    el('div',{class:'stats'},[['10','Flexible cards'],['6','Curated looks'],['100%','Local settings']].map(([n,l])=>el('div',{class:'stat'},el('strong',{text:n}),el('small',{text:l})))),
    section('Start with a feeling','Six considered palettes. One completely personal space.',themes()),
    !state.eww?section('Finish connecting your desktop','The customization studio works now. Install EWW 0.6+ to use the desktop widgets.',button('Check requirements',()=>navigate('maintenance'))):null];
}
function appearance() {
  return [...title('SET THE MOOD','Beautiful by default. Uniquely yours.','Fine-tune every surface, from the accent that catches your eye to the space between your cards.'),section('Curated looks','Choosing a preset resets the accent color and appearance mode.',themes()),
    section('Color & surface','',field('appearance.mode','Appearance','',{choices:[['dark','Dark'],['light','Light']]}),el('div',{class:'inline'},field('appearance.accent','Custom accent','Blank uses the preset color.'),el('input',{type:'color',value:draft.appearance.accent||state.themes[draft.appearance.preset][4],'aria-label':'Choose accent color',oninput:e=>{put('appearance.accent',e.target.value);}})),el('div',{class:'split'},field('appearance.radius','Corner radius','0–36 pixels',{type:'number',min:0,max:36}),field('appearance.opacity','Surface opacity','70–100%',{type:'number',min:70,max:100})),toggle('appearance.shadow','Soft shadows'),picker('appearance.background','Background image','image')),
    section('Type & comfort','Legible, calm, and easy to use.',field('appearance.font','Font family','Use any installed family, e.g. Sans, Inter, Noto Sans.'),field('appearance.font_size','Text size','11–24 pixels. Larger text may need fewer columns.',{type:'number',min:11,max:24}),toggle('appearance.reduced_motion','Reduce motion','Disables dashboard transitions.'),toggle('appearance.high_contrast','High contrast','Stronger separation and text contrast.'))];
}
function layout() {
  const list=el('div');draft.layout.cards.forEach((card,i)=>{
    list.append(el('div',{class:'order-row'},el('input',{type:'checkbox',checked:card.enabled,'aria-label':'Show '+card.label,onchange:e=>put(`layout.cards.${i}.enabled`,e.target.checked)}),field(`layout.cards.${i}.label`,card.id),el('button',{text:'↑',disabled:i===0,'aria-label':'Move '+card.label+' up',onclick:()=>moveCard(i,-1)}),el('button',{text:'↓',disabled:i===draft.layout.cards.length-1,'aria-label':'Move '+card.label+' down',onclick:()=>moveCard(i,1)})));
  });
  return [...title('SPACE TO BREATHE','A place for everything you love.','Show, hide, rename, and reorder your cards. The desktop scrolls comfortably when everything doesn’t fit.'),section('Layout','Use one or two columns on smaller displays; three on a typical desktop.',el('div',{class:'split'},field('layout.columns','Columns','',{choices:[[1,'One · focused'],[2,'Two · compact'],[3,'Three · balanced'],[4,'Four · wide']],numeric:true}),field('layout.density','Spacing','',{choices:['compact','balanced','spacious']})),field('layout.monitor','Monitor','Use 0 for your first monitor, an output name such as DP-1, or <primary>.'),el('div',{class:'split'},field('layout.width','Window width','Percentage of the selected screen.',{type:'number',min:50,max:100}),field('layout.height','Window height','Percentage of the selected screen.',{type:'number',min:50,max:100}))),section('Your cards','Changes follow reading order, left to right, then down.',list)];
}
function moveCard(i,d) { [draft.layout.cards[i],draft.layout.cards[i+d]]=[draft.layout.cards[i+d],draft.layout.cards[i]];changed();show(); }
function personal() {
  return [...title('THE PERSONAL TOUCH','Your name on the door.','A familiar greeting and the time, exactly how you like it.'),section('Profile','',field('profile.name','Display name'),field('profile.caption','A little message'),toggle('profile.show_username','Show system username'),picker('profile.image','Profile image','image')),section('Clock','',field('clock.format','Time format','',{choices:[['24h','24-hour'],['12h','12-hour']]}),field('clock.timezone','Time zone','Blank follows your computer. Example: Europe/London.'),field('clock.date_format','Date format','Examples: %A, %d %B or %Y-%m-%d.'))];
}
function weather() {
  const search=el('input',{placeholder:'Search city, e.g. Copenhagen','aria-label':'City name'});const results=el('div');
  async function lookup() { results.textContent='Looking for your city…';try {const data=await api('search',{query:search.value});results.replaceChildren(...data.results.map(x=>button(x.name,()=>{put('weather.place',x.name);put('weather.latitude',x.latitude);put('weather.longitude',x.longitude);show();},'result')));if(!data.results.length)results.textContent='No matches. Try a nearby city.';}catch(error){results.textContent=error.message;} }
  search.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();lookup();}});
  return [...title('A LITTLE OUTSIDE, INSIDE','Bring your forecast closer.','Search for a city—no API key or coordinates needed. Searches and forecasts use Open-Meteo; your location is only sent when you choose it.'),section('Find your city','',search,button('Search cities',lookup),results,field('weather.place','Location label'),button('Turn weather off',()=>{put('weather.latitude','');put('weather.longitude','');put('weather.place','');show();},'ghost')),section('Forecast preferences','',field('weather.unit','Temperature','',{choices:[['metric','Celsius · °C'],['imperial','Fahrenheit · °F']]}),field('weather.refresh','Refresh every (seconds)','At least 60 seconds. Last successful reading is kept when offline.',{type:'number',min:60,max:86400}),el('details',{},el('summary',{text:'Enter coordinates manually'}),el('div',{class:'split'},field('weather.latitude','Latitude','−90 to 90'),field('weather.longitude','Longitude','−180 to 180'))))];
}
function integrations() {
  return [...title('IN TUNE WITH YOUR DESKTOP','The essentials, working together.','Orbit detects available players and audio tools. Optional integrations can be added whenever you need them.'),section('Music','MPRIS through playerctl, with MPD as a fallback.',field('music.player','Preferred MPRIS player','Blank automatically prefers a playing player over a paused one.'),picker('music.directory','MPD music directory','folder'),el('div',{class:'split'},field('music.seek_seconds','Seek step (seconds)','Scroll over progress to seek.',{type:'number',min:1,max:60}),field('music.refresh','Refresh (seconds)','',{type:'number',min:2,max:60}))),section('System','',picker('system.disk','Disk / mount point','folder'),field('system.refresh','Refresh (seconds)','',{type:'number',min:2,max:60}),toggle('system.updates','Check for package updates','Cached; supports checkupdates, apt and Flatpak.')),section('Interaction','',toggle('behavior.close_on_launch','Close dashboard after opening a shortcut'),toggle('behavior.confirm_power','Confirm power actions','Recommended for suspend, restart, and power off.'),toggle('behavior.lock_before_suspend','Lock before suspend','Suspend is cancelled if no working lock command is available.'))];
}
function shortcuts(kind) {
  const names={apps:['YOUR LAUNCHPAD','Everything you need, one click away.','Choose installed applications. Custom shell commands are available when Advanced mode is enabled.'],links:['SHORTCUTS TO THE WEB','A few favorites. Always within reach.','Add up to 24 links. Use complete https:// addresses.'],folders:['FAMILIAR PLACES','Find your way home.','Use any local folder. Missing folders show a helpful message rather than being created automatically.']};
  const rows=draft[kind].map((row,i)=>{
    const content=[el('div',{class:'item-head'},el('strong',{text:row.label||'New shortcut'}),el('div',{class:'inline'},button('↑',()=>{if(i){[draft[kind][i-1],draft[kind][i]]=[draft[kind][i],draft[kind][i-1]];changed();show();}}),button('Test saved',async()=>{if(dirty())throw new Error('Save your changes before testing a shortcut.');const r=await api('test',{collection:kind,index:i});message(r.message);}),button('Remove',()=>{draft[kind].splice(i,1);changed();show();},'danger'))),el('div',{class:'split'},field(`${kind}.${i}.label`,'Name'),field(`${kind}.${i}.icon`,'Icon text','Up to 8 characters or a symbol.')),toggle(`${kind}.${i}.enabled`,'Show shortcut')];
    if(kind==='apps'){
      const choices=[['default','System default'],['desktop','Installed application'],['command','Advanced command']];
      const select=el('select',{value:row.kind,onchange:e=>{row.kind=e.target.value;row.target=row.kind==='default'?'browser':row.kind==='desktop'?(state.apps[0]?.id||''):'';changed();show();}},choices.map(x=>el('option',{value:x[0],text:x[1]})));select.value=row.kind;
      content.push(el('label',{class:'field'},el('span',{text:'Open with'}),select));
      if(row.kind==='desktop')content.push(field(`${kind}.${i}.target`,'Application','Detected from your desktop application menu.',{choices:state.apps.map(a=>[a.id,a.name])}));
      else if(row.kind==='default')content.push(field(`${kind}.${i}.target`,'Default application','',{choices:[['browser','Browser'],['files','File manager'],['terminal','Terminal']]}));
      else content.push(field(`${kind}.${i}.target`,'Shell command',draft.advanced.enabled?'Runs with your user permissions.':'Disabled until you enable Advanced mode.'));
    } else if(kind==='links')content.push(field(`${kind}.${i}.url`,'Website address'));
    else content.push(picker(`${kind}.${i}.path`,'Folder','folder'));
    return el('div',{class:'item'},content);
  });
  return [...title(...names[kind]),...rows,button('+ Add shortcut',()=>{if(draft[kind].length>=24)throw new Error('You can add up to 24 shortcuts.');const row={label:'New shortcut',icon:kind==='links'?'↗':'DIR',enabled:true};if(kind==='apps')Object.assign(row,{kind:'default',target:'browser'});else if(kind==='links')row.url='https://example.com';else row.path='';draft[kind].push(row);changed();show();},'primary')];
}
function advanced() {
  return [...title('A LITTLE MORE CONTROL','For the way you work.','Normal shortcuts use installed apps and argument-safe launchers. Here you can opt in to your own trusted shell commands.'),section('Advanced commands','Commands run as your user. Imported and migrated commands start disabled. URLs and folder paths are passed as arguments, not inserted into command text.',toggle('advanced.enabled','Enable custom shell commands'),field('advanced.browser','Browser command','Example: firefox. A URL is appended as an argument.'),field('advanced.file_manager','File manager command','Example: dolphin. A folder is appended as an argument.'),field('advanced.terminal','Terminal command','Example: kitty.'),field('advanced.update_command','Update command','Runs in a detected terminal. Example: sudo apt update && sudo apt upgrade.')),section('Your configuration','Versioned JSON is validated before it is saved. Legacy shell configuration is imported as data and never executed.',el('pre',{text:state.path}))];
}
function maintenance() {
  const diagnostics=el('pre',{text:'Run diagnostics to check your installation and optional integrations.'});
  const backups=el('div',{},state.backups.length?state.backups.map(name=>button(new Date(Number(name.split('.')[0])/1e6).toLocaleString()+' · Restore',async()=>{if(!confirm('Restore this backup? Current settings will be backed up first.'))return;const r=await api('restore',{name,revision:state.revision});await accept(r);},'result')):el('p',{class:'help',text:'Your first backup appears after you save changes to an existing configuration.'}));
  return [...title('PEACE OF MIND','Experiment. You can always go back.','Every save keeps a backup. Export your setup, try a new look, or restore a familiar one.'),section('Take your space with you','Exports contain your preferences and local paths, not image files. Imported shell commands stay disabled until you enable them.',el('div',{class:'inline'},button('Export settings',()=>{const blob=new Blob([JSON.stringify(draft,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=el('a',{href:url,download:'orbit-settings.json'});a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}),button('Import settings',()=>$('#import-file').click()))),section('Recent backups','The 20 most recent settings versions are kept.',backups),section('Installation health','A missing optional player or audio tool does not prevent Orbit from opening.',button('Run diagnostics',async()=>{diagnostics.textContent='Checking…';const r=await api('diagnostics');diagnostics.textContent=r.output;}),diagnostics),section('A fresh start','Reset to the curated default. Your current settings are backed up first.',button('Reset all settings',async()=>{if(confirm('Reset all settings to defaults? A backup will be saved.'))await accept(await api('reset',{revision:state.revision}));},'danger'))];
}
function show() {
  $('#navigation').replaceChildren(...pages.map(([id,icon,label])=>el('button',{class:page===id?'active':'','aria-current':page===id?'page':'false','aria-label':label,onclick:()=>navigate(id)},el('span',{text:icon}),label)));
  $('#breadcrumb').textContent='Your workspace / '+pages.find(x=>x[0]===page)[2];
  const factory={overview,appearance,layout,personal,weather,integrations,apps:()=>shortcuts('apps'),links:()=>shortcuts('links'),folders:()=>shortcuts('folders'),advanced,maintenance};
  $('#content').replaceChildren(...factory[page]().filter(Boolean));
  if(page==='integrations') $('#content').append(section('Album artwork','PNG and JPEG covers are cached locally; unavailable covers use the bundled fallback.',toggle('music.artwork','Show album artwork')));
  if(page==='layout' && state.monitors?.length) {
    $('#content').append(section('Detected displays','Pick a connected screen. Columns automatically reduce on smaller screens or at larger text sizes.',el('div',{class:'inline'},state.monitors.map(m=>button(`${m.name} · ${m.width} × ${m.height}`,()=>{put('layout.monitor',m.name);show();})))));
  }
  changed();
}
function navigate(id) { page=id;show();$('#content').focus({preventScroll:true});window.scrollTo({top:0}); }
function preview() {
  if(!draft)return;const p=$('#preview');const a=draft.appearance;let colors=[...state.themes[a.preset]];
  if(a.mode==='light'){colors.splice(0,4,'#edf0f5','#ffffff','#172033','#536174');colors[4]={aurora:'#236653',midnight:'#6542b2',graphite:'#46536a',ember:'#994327',ocean:'#186981',minimal:'#346759'}[a.preset];}
  else if(a.preset==='minimal')colors.splice(0,4,...state.themes.graphite.slice(0,4));
  if(a.high_contrast)colors.splice(0,4,...(a.mode==='light'?['#ffffff','#ffffff','#000000','#252525']:['#000000','#0b0b0b','#ffffff','#eeeeee']));
  if(a.accent)colors[4]=a.accent;if(a.high_contrast)colors[4]=a.mode==='light'?'#174f3e':'#b4ffdd';['bg','surface','text','muted','accent'].forEach((k,i)=>p.style.setProperty('--preview-'+k,colors[i]));p.style.setProperty('--preview-radius',Math.min(a.radius,20)+'px');
  const grid=el('div',{class:'preview-grid'});grid.style.gridTemplateColumns=`repeat(${draft.layout.columns},minmax(0,1fr))`;
  const samples={profile:[draft.profile.name,draft.profile.caption],clock:[draft.clock.format==='24h'?'14:38':'02:38 PM','Tuesday, 16 June'],system:['All in balance','CPU 24% · Memory 48%'],weather:['21°C',draft.weather.place||'Choose your city'],music:['A little atmosphere','Your favorite player'],uptime:['2h 34m','Since last restart'],power:['☾   ↻   ⏻','Take a break']};
  draft.layout.cards.filter(c=>c.enabled).forEach(card=>{const content=samples[card.id]||[draft[card.id]?.filter(x=>x.enabled).slice(0,3).map(x=>x.icon||x.label).join('   ')||'Add your favorites',draft[card.id]?.filter(x=>x.enabled).map(x=>x.label).slice(0,3).join(' · ')||'Customize this space'];const c=el('div',{class:'mini-card'},el('small',{text:card.label}),el('strong',{text:content[0]}),el('p',{text:content[1]}));if(card.id==='system'||card.id==='music')c.append(el('div',{class:'mini-progress'},el('i')));grid.append(c);});
  p.replaceChildren(el('div',{class:'preview-head'},'◉ ORBIT',el('span',{text:'•••'})),grid);
}
async function accept(result) { const refreshed=await api('state');state=refreshed;draft=clone(refreshed.settings);saved=clone(draft);show();message(result.message||'Settings restored.'); }
$('#save').addEventListener('click',()=>attempt(async()=>{busy=true;changed();try {draft.setup_complete=true;const result=await api('save',{settings:draft,revision:state.revision});await accept(result);}finally{busy=false;changed();}}));
$('#discard').addEventListener('click',()=>{draft=clone(saved);show();message('Unsaved changes discarded.');});
$('#open-dashboard').addEventListener('click',()=>attempt(async()=>message((await api('dashboard',{})).message)));
$('#import-file').addEventListener('change',e=>attempt(async()=>{const file=e.target.files[0];if(!file)return;if(file.size>200000)throw new Error('Choose an Orbit settings JSON file smaller than 200 KB.');const data=JSON.parse(await file.text());const imported=await api('import',{settings:data});draft=imported.settings;show();message('Imported into your draft. Review your settings, then Save & apply. Advanced commands are disabled.');e.target.value='';}));
window.addEventListener('beforeunload',e=>{if(draft&&dirty()){e.preventDefault();e.returnValue='';}});
attempt(async()=>{state=await api('state');draft=clone(state.settings);saved=clone(draft);show();if(state.error)message('Your existing file needs repair. The default preview is shown; saving will back up the original.\n'+state.error,true);else if(state.migration_notes?.length)message('Legacy settings imported into your draft. Review these unsupported entries in the original file: '+state.migration_notes.join(', '));});
