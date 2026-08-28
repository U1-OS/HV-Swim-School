(() => {
  'use strict';
  const applySiteSettings=async()=>{
    try{
      const response=await fetch('/api/public/site-settings',{headers:{Accept:'application/json'}});if(!response.ok)return;
      const {settings={}}=await response.json();
      document.querySelectorAll('[data-site-field]').forEach(element=>{const value=settings[element.dataset.siteField];if(value)element.textContent=value;});
      const announcement=document.getElementById('site-announcement');
      if(announcement&&settings.announcement_enabled){
        document.getElementById('site-announcement-text').textContent=settings.announcement_text;
        document.getElementById('site-enrolment-status').textContent=({open:'Enrolments open',limited:'Limited places',waitlist:'Waitlist only'})[settings.enrolment_status]||'Enrolment update';
        announcement.hidden=false;
      }
    }catch(_){}
  };
  applySiteSettings();
  // The lesson-finder widget and the old single-page enquiry form that used to live
  // here were replaced by the four-step wizard in enquire.js. Their code was left
  // behind, pointing at eight elements that no longer exist on any page, and it has
  // already misled two separate reviews. Removed.

  const availability=document.getElementById('public-availability');
  if(availability){
    const days=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
    const esc=value=>String(value??'').replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
    fetch('/api/classes',{headers:{Accept:'application/json'}}).then(async response=>{
      const payload=await response.json();if(!response.ok)throw new Error(payload.detail||'Availability unavailable');
      const open=(payload.classes||[]).filter(item=>Number(item.available)>0).slice(0,6);
      availability.innerHTML=open.map((item,index)=>{const query=new URLSearchParams({program:item.title,class:`${days[item.weekday]} ${item.start_time} at ${item.location_name}`});return `<article class="availability-card reveal visible" style="--reveal-delay:${Math.min(index*60,240)}ms"><span class="class-day">${esc(days[item.weekday])} · ${esc(item.start_time)}</span><h3>${esc(item.title)}</h3><p>${esc(item.level)} · ${esc(item.duration_minutes)} minutes<br>${esc(item.location_name)}</p><div class="availability-card-foot"><div><strong>${item.available} ${item.available===1?'place':'places'} showing</strong><span>${new Intl.NumberFormat('en-AU',{style:'currency',currency:'AUD'}).format(Number(item.price||0))} per lesson · preview</span></div><a class="text-link" href="enquire.html?${query}">Enquire</a></div></article>`;}).join('')||'<div class="empty-state"><strong>No classes are showing places right now.</strong><p>Places open up through the term as families change days. Send an enquiry and we will let you know as soon as one does.</p><a class="btn btn-blue btn-small" href="enquire.html">Join the list <span aria-hidden="true">&rarr;</span></a></div>';
      document.getElementById('availability-source').textContent='Connected to the local class database. Places and prices remain preview data until HV Swim imports the approved live timetable.';
    }).catch(()=>{
      availability.innerHTML='<div class="empty-state"><strong>Class times are not loading right now.</strong><p>This is a temporary problem on our side, not a sign that classes are full. Tell us what you are after and we will come back to you with what is open.</p><a class="btn btn-blue btn-small" href="enquire.html">Find a lesson <span aria-hidden="true">&rarr;</span></a></div>';
      const badge=document.getElementById('availability-connection');
      if(badge){badge.textContent='Timetable unavailable';badge.classList.remove('open');badge.classList.add('changed');}
      const note=document.getElementById('availability-connection-note');
      if(note){note.textContent='We could not reach the class database. Please use the lesson finder or call the team.';}
    });
  }

  const todayGrid=document.getElementById('today-grid');
  if(todayGrid){
    const days=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
    const weatherLabel=code=>({0:'Clear',1:'Mostly clear',2:'Partly cloudy',3:'Overcast',45:'Foggy',48:'Foggy',51:'Light drizzle',53:'Drizzle',55:'Heavy drizzle',61:'Light rain',63:'Rain',65:'Heavy rain',71:'Light snow',80:'Rain showers',81:'Rain showers',82:'Heavy showers',95:'Thunderstorm'})[Number(code)]||'Local conditions';
    const formatTime=value=>{try{return new Intl.DateTimeFormat('en-AU',{day:'numeric',month:'short',hour:'numeric',minute:'2-digit',timeZone:'Australia/Melbourne'}).format(new Date(value));}catch(_){return'Update time unavailable';}};
    Promise.all([
      fetch('/api/public/weather',{headers:{Accept:'application/json'}}).then(response=>response.ok?response.json():Promise.reject()),
      fetch('/api/public/locations',{headers:{Accept:'application/json'}}).then(response=>response.ok?response.json():Promise.reject()),
      fetch('/api/classes',{headers:{Accept:'application/json'}}).then(response=>response.ok?response.json():Promise.reject())
    ]).then(([weather,locationData,classData])=>{
      const current=weather.current||{};
      document.getElementById('today-weather-temp').textContent=`${Number(current.temperature_2m).toFixed(1)}°C`;
      document.getElementById('today-weather-detail').textContent=`${weatherLabel(current.weather_code)} · feels like ${Number(current.apparent_temperature).toFixed(1)}°C · wind ${Number(current.wind_speed_10m).toFixed(0)} km/h`;
      const locations=locationData.locations||[];
      const wood=locations.find(item=>item.slug==='wood-street'); const reading=wood?.latest_reading;
      document.getElementById('today-pool-temp').textContent=reading?.temperature!=null?`${Number(reading.temperature).toFixed(1)}°C`:'Update due';
      document.getElementById('today-pool-detail').textContent=reading?`${locationData.locations.find(item=>item.slug==='wood-street')?.reading_stale?'Reading over 24h old':'Staff verified'} · ${formatTime(reading.created_at)} · ${reading.first_name||'HV Swim team'}`:'No current staff reading published';
      const seasonal=locations.find(item=>item.slug==='bendigo-east');
      document.getElementById('today-seasonal-copy').textContent=seasonal?.public_status||'Status unavailable';
      const seasonalStatus=document.getElementById('today-seasonal-status');seasonalStatus.textContent=seasonal?.public_status?.toLowerCase().includes('closed')?'Closed':'Venue update';seasonalStatus.className=`status ${seasonal?.public_status?.toLowerCase().includes('closed')?'closed':'changed'}`;
      const now=new Date();const currentDay=(now.getDay()+6)%7;const currentMinutes=now.getHours()*60+now.getMinutes();
      const open=(classData.classes||[]).filter(item=>Number(item.available)>0).map(item=>{const [hour,minute]=String(item.start_time).split(':').map(Number);let dayDelta=(Number(item.weekday)-currentDay+7)%7;if(dayDelta===0&&hour*60+minute<=currentMinutes)dayDelta=7;return{...item,sort:dayDelta*1440+hour*60+minute};}).sort((a,b)=>a.sort-b.sort);
      const next=open[0];
      if(next){
        document.getElementById('today-class-title').textContent=next.title;
        document.getElementById('today-class-detail').textContent=`${days[next.weekday]} ${next.start_time} · ${next.location_name} · ${next.available} ${next.available===1?'place':'places'} showing`;
        document.getElementById('today-class-link').href=`enquire.html?${new URLSearchParams({program:next.title,class:`${days[next.weekday]} ${next.start_time} at ${next.location_name}`})}`;
      }else{document.getElementById('today-class-title').textContent='Ask the team';document.getElementById('today-class-detail').textContent='No open class is currently showing in the preview timetable.';}
      document.getElementById('today-updated').textContent=`Updated ${new Intl.DateTimeFormat('en-AU',{hour:'numeric',minute:'2-digit'}).format(new Date())}`;
    }).catch(()=>{
      document.getElementById('today-weather-detail').textContent='Live weather is temporarily unavailable.';
      document.getElementById('today-pool-detail').textContent='Open Locations for the latest published condition.';
      document.getElementById('today-class-detail').textContent='The team can confirm current lesson options.';
      document.getElementById('today-updated').textContent='Connection unavailable';
    });
  }
})();
