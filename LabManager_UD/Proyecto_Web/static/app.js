document.addEventListener('DOMContentLoaded',()=>{
  const batch=document.getElementById('batch-maintenance');
  if(batch){
    const checks=Array.from(batch.querySelectorAll('[name=equipos]'));
    const summary=document.getElementById('time-summary');
    const minutes=value=>{if(!value)return null;const [h,m]=value.split(':').map(Number);return h*60+m;};
    const update=()=>{const count=checks.filter(c=>c.checked).length,start=minutes(batch.elements.hora_inicio.value),end=minutes(batch.elements.hora_fin.value);summary.textContent=start!==null&&end!==null&&end>start&&count ? `${count} equipos · ${end-start} minutos en total · ${((end-start)/count).toLocaleString('es-CO',{maximumFractionDigits:2})} minutos por reporte.` : 'Marca equipos e indica una hora de fin posterior a la de inicio para ver el reparto.';};
    batch.addEventListener('change',update);update();
    document.getElementById('equipment-search').addEventListener('input',event=>{const q=event.target.value.toLocaleLowerCase();checks.forEach(c=>{const row=c.closest('div');row.hidden=!row.textContent.toLocaleLowerCase().includes(q);});});
  }
  const current=location.pathname;
  const navigation=Array.from(document.querySelectorAll('.sidebar nav a'));
  navigation.forEach(a=>{a.classList.remove('active');a.removeAttribute('aria-current');});
  const selected=navigation.map(a=>({a,target:new URL(a.href).pathname})).filter(({target})=>target===current||(target!=='/'&&current.startsWith(target.endsWith('/')?target:target+'/'))).sort((a,b)=>b.target.length-a.target.length)[0];
  if(selected){selected.a.classList.add('active');selected.a.setAttribute('aria-current','page');const group=selected.a.closest('details');if(group)group.open=true;}
  const menu=document.querySelector('.menu-toggle');if(menu)menu.addEventListener('click',()=>{const open=menu.getAttribute('aria-expanded')!=='true';menu.setAttribute('aria-expanded',String(open));document.getElementById('main-navigation').classList.toggle('is-open',open);});
  document.querySelectorAll('.form-field').forEach(field=>{if(field.querySelector('textarea, [type=file], [type=checkbox]'))field.classList.add('full-width');});
  const stateOf=text=>{
    const value=text.normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().toLocaleLowerCase();
    if(/obsolet|danad|inactiv|no operativ|no activ|fuera de servicio|cancelad|rechazad|error|averiad|baja/.test(value))return 'danger';
    if(/pendiente|reparaci|mantenimiento|revision/.test(value)&&!/asignad/.test(value))return 'warning';
    if(/asignad|en curso|procesando|proceso de traslado/.test(value))return 'progress';
    if(/^(activo|activos|operativo|operativos|funcional|en servicio)$|finalizad|cerrad|aprobad|completad/.test(value))return 'success';
    return 'neutral';
  };
  document.querySelectorAll('.badge:not(.maintenance-type)').forEach(b=>{b.dataset.state=stateOf(b.textContent);});
  document.querySelectorAll('.metric').forEach(metric=>{metric.dataset.state=stateOf(metric.querySelector('span')?.textContent||'');});
  document.querySelectorAll('select[name=estado]').forEach(select=>{const update=()=>{select.dataset.state=stateOf(select.value);};select.addEventListener('change',update);update();});
  document.querySelectorAll('select').forEach(select=>{
    if(select.multiple||select.disabled||(select.name!=='equipo'&&select.options.length<25))return;
    const options=Array.from(select.options).filter(o=>o.value&&!o.disabled).map(o=>({text:o.text,value:o.value}));
    const normalize=value=>value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase();
    const wrap=document.createElement('div');wrap.className='autocomplete';
    const search=document.createElement('input');search.type='text';search.autocomplete='off';search.spellcheck=false;search.className='autocomplete-input';
    search.id=select.id+'-search';search.placeholder=select.name==='equipo'?'Busca por placa, interno o nombre':'Escribe para buscar';
    search.required=select.required;
    const list=document.createElement('div');list.id=search.id+'-options';list.className='autocomplete-options';list.hidden=true;list.setAttribute('role','listbox');
    search.setAttribute('role','combobox');search.setAttribute('aria-autocomplete','list');search.setAttribute('aria-expanded','false');search.setAttribute('aria-controls',list.id);
    const label=Array.from(document.querySelectorAll('label')).find(label=>label.htmlFor===select.id);
    if(label)label.htmlFor=search.id;else search.setAttribute('aria-label','Buscar '+select.name);
    select.before(wrap);wrap.append(search,list);select.hidden=true;select.required=false;select.tabIndex=-1;
    let matches=[],active=-1;
    const close=()=>{list.hidden=true;search.setAttribute('aria-expanded','false');search.removeAttribute('aria-activedescendant');active=-1;};
    const choose=option=>{select.value=option.value;search.value=option.text;search.setCustomValidity('');select.dispatchEvent(new Event('change',{bubbles:true}));close();};
    const render=()=>{
      const words=normalize(search.value).trim().split(/\s+/).filter(Boolean);
      matches=options.filter(o=>words.every(word=>normalize(o.text).includes(word))).slice(0,40);active=-1;list.replaceChildren();
      matches.forEach((option,index)=>{const item=document.createElement('div');item.className='autocomplete-option';item.id=list.id+'-'+index;item.setAttribute('role','option');item.setAttribute('aria-selected','false');item.textContent=option.text;item.addEventListener('mousedown',e=>e.preventDefault());item.addEventListener('click',()=>choose(option));list.append(item);});
      if(!matches.length){const empty=document.createElement('div');empty.className='autocomplete-empty';empty.textContent='No hay coincidencias. Prueba con otra placa o nombre.';list.append(empty);}
      list.hidden=false;search.setAttribute('aria-expanded','true');search.removeAttribute('aria-activedescendant');
    };
    const sync=()=>{search.value=options.find(o=>o.value===select.value)?.text||'';search.setCustomValidity('');close();};sync();
    search.addEventListener('focus',render);
    search.addEventListener('input',()=>{select.value='';search.setCustomValidity(search.value?'Selecciona un equipo de las opciones.':'');render();});
    search.addEventListener('keydown',event=>{
      if(event.key==='Escape'){close();return;}
      if(event.key==='ArrowDown'||event.key==='ArrowUp'){
        event.preventDefault();if(list.hidden)render();if(!matches.length)return;
        active=(active+(event.key==='ArrowDown'?1:-1)+matches.length)%matches.length;
        Array.from(list.children).forEach((item,index)=>item.setAttribute('aria-selected',String(index===active)));
        const item=list.children[active];search.setAttribute('aria-activedescendant',item.id);item.scrollIntoView({block:'nearest'});
      }else if(event.key==='Enter'&&!list.hidden){event.preventDefault();if(active>=0)choose(matches[active]);else if(matches.length===1)choose(matches[0]);}
    });
    search.addEventListener('blur',()=>setTimeout(close,150));
    select.addEventListener('change',sync);
    select.form?.addEventListener('reset',()=>setTimeout(sync,0));
  });
  document.querySelectorAll('[data-print]').forEach(b=>b.addEventListener('click',()=>window.print()));
});

// Actualiza la alerta sin interrumpir formularios o navegación.
(() => {
  const alert = document.getElementById('transfer-alert');
  if (!alert) return;
  async function refresh() {
    if (document.hidden) return;
    try {
      const response = await fetch(alert.dataset.url, {headers: {'Accept': 'application/json'}});
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) return;
      const data = await response.json();
      const badge = document.getElementById('transfer-count');
      if (badge) {badge.textContent = data.pendientes; badge.hidden = data.pendientes === 0;}
      const requests = document.getElementById('request-count');
      if (requests && Number.isInteger(data.solicitudes)) {requests.textContent = data.solicitudes; requests.hidden = data.solicitudes === 0;}
    } catch (_) { /* Se reintenta en el próximo intervalo. */ }
  }
  setInterval(refresh, 30000);
})();

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-row-url]').forEach(row => {
    row.addEventListener('click', event => {
      if (event.target.closest('a, button, input, select, textarea, form') || window.getSelection().toString()) return;
      if (event.ctrlKey || event.metaKey) window.open(row.dataset.rowUrl, '_blank', 'noopener');
      else window.location.assign(row.dataset.rowUrl);
    });
  });
});
