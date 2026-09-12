(() => {
'use strict';
const expectedRole = document.body.dataset.deskRole;
if (!expectedRole) return;
const content = document.getElementById('desk-content');
const feedback = document.getElementById('desk-feedback');
const dialog = document.getElementById('desk-dialog');
const dialogContent = document.getElementById('desk-dialog-content');
let user, csrf, routeId = 0, timer, opener, rosterData, leaveData, documentData;
let clockData, clockRequest, busy = false;
const management = expectedRole === 'admin';
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const icon = name => '<svg class="ui-icon" aria-hidden="true"><use href="assets/icons.svg#'+esc(name)+'"></use></svg>';
const today = () => {const p=new Intl.DateTimeFormat('en-AU',{timeZone:'Australia/Melbourne',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());return ['year','month','day'].map(k=>p.find(v=>v.type===k).value).join('-');};
const addDays = (date, amount) => { const value = new Date(date+'T12:00:00Z');value.setUTCDate(value.getUTCDate()+amount);return value.toISOString().slice(0,10); };
const monday = date => {const value = new Date(date+'T12:00:00Z');return addDays(date,-((value.getUTCDay()+6)%7));};
let weekStart = monday(today());
const dateLabel = value => value ? new Intl.DateTimeFormat('en-AU',{day:'numeric',month:'short',year:'numeric',timeZone:'Australia/Melbourne'}).format(new Date(String(value).slice(0,10)+'T00:00:00+10:00')) : 'Not supplied';
const stamp = value => value && !Number.isNaN(Date.parse(value)) ? new Intl.DateTimeFormat('en-AU',{day:'numeric',month:'short',hour:'numeric',minute:'2-digit',timeZone:'Australia/Melbourne'}).format(new Date(value)) : '—';
const timeLabel = value => { const [h,m] = String(value||'').split(':').map(Number); return Number.isInteger(h) ? (h%12||12)+':'+String(m).padStart(2,'0')+(h<12?' am':' pm') : '—'; };
const hours = seconds => (Number(seconds||0)/3600).toFixed(2);
const chip = state => '<span class="desk-chip" data-state="'+esc(state)+'">'+esc(String(state||'pending').replaceAll('_',' '))+'</span>';
const empty = message => '<div class="desk-empty">'+esc(message)+'</div>';
const button = (text, action, data='', style='secondary') => '<button type="button" class="desk-button" data-variant="'+esc(style)+'" data-action="'+action+'" '+data+'>'+text+'</button>';
const field = (label,name,type='text',value='',extra='') => '<label class="desk-field"><span>'+label+'</span><input type="'+type+'" name="'+name+'" value="'+esc(value)+'" '+extra+'></label>';
const select = (label,name,options,value='',extra='') => '<label class="desk-field"><span>'+label+'</span><select name="'+name+'" '+extra+'>'+options.map(([v,t])=>'<option value="'+esc(v)+'" '+(String(v)===String(value)?'selected':'')+'>'+esc(t)+'</option>').join('')+'</select></label>';
const heading = (eyebrow,title,description,action='') => '<div class="desk-heading"><div><div class="eyebrow">'+eyebrow+'</div><h1>'+title+'</h1><p>'+description+'</p></div>'+action+'</div>';
const nameOf = row => [row.first_name,row.last_name].filter(Boolean).join(' ');
function notice(message,error=false,target=feedback){target.textContent=message;target.dataset.error=String(error);target.hidden=false;}
function clearNotice(){feedback.hidden=true;}
async function api(path, options={}) {
 const controller = new AbortController(), timeout = setTimeout(()=>controller.abort(),20000);
 try {
  const response = await fetch(path,{...options,credentials:'same-origin',cache:'no-store',signal:controller.signal,headers:{Accept:'application/json',...(options.body?{'Content-Type':'application/json'}:{}),...(csrf?{'X-CSRF-Token':csrf}:{}),...options.headers}});
  let data;try{data=await response.json();}catch(_){throw new Error('The service returned an unreadable response. Please try again.');}
  if(response.status===401){location.href='login.html?role='+expectedRole;throw new Error('Please sign in again.');}
  if(!response.ok)throw new Error(Array.isArray(data.detail)?data.detail.map(e=>e.msg).join(' '):(data.detail||'The request could not be completed.'));
  return data;
 } catch(error){if(error.name==='AbortError')throw new Error('The connection timed out. Refresh to check the saved state before retrying.');throw error;}
 finally{clearTimeout(timeout);}
}
const post = (path,data) => api(path,{method:'POST',body:JSON.stringify(data)});
function openDialog(title,description,body,trigger){
 opener=trigger||document.activeElement;
 dialogContent.innerHTML='<h2 id="desk-dialog-title">'+esc(title)+'</h2><p>'+esc(description)+'</p>'+body+'<div class="desk-feedback" data-dialog-feedback role="alert" hidden></div>';
 dialog.showModal();dialog.querySelector('input,select,button')?.focus();
}
function closeDialog(){dialog.close();dialogContent.innerHTML='';opener?.focus?.();}
document.querySelector('.desk-dialog-close').addEventListener('click',()=>{if(!busy)closeDialog();});
dialog.addEventListener('cancel',event=>{if(busy){event.preventDefault();return;}});
dialog.addEventListener('close',()=>{opener?.focus?.();});
const routes = management ? [['roster','calendar','Roster planner'],['leave','calendar','Time off'],['availability','bell','Shift notices'],['documents','document','Documents'],['profile','users','My details']] : [['home','home','My workday'],['roster','calendar','My roster'],['hours','clock','My hours'],['leave','calendar','Time off'],['availability','bell','Shift notices'],['documents','document','My documents'],['profile','users','My details']];
function nav(){
 document.getElementById('desk-nav').innerHTML=routes.map(([id,symbol,label])=>'<a href="#'+id+'">'+icon(symbol)+esc(label)+'</a>').join('');
}
async function render(){
 clearInterval(timer);const id=++routeId;clearNotice();
 const key=routes.some(r=>r[0]===location.hash.slice(1))?location.hash.slice(1):routes[0][0];
 document.title=(routes.find(r=>r[0]===key)?.[2]||'Workspace')+' | HV Swim Bendigo';
 document.querySelectorAll('#desk-nav a').forEach(a=>{if(a.hash==='#'+key)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
 content.innerHTML='<div class="desk-card"><p role="status">Loading your '+esc(key==='home'?'workday':key)+'…</p></div>';
 try{
  const html=await ({home:renderHome,roster:renderRoster,hours:renderHours,leave:renderLeave,documents:renderDocuments,profile:renderProfile,availability:renderAvailability})[key]();
  if(id!==routeId)return;content.innerHTML=html;
  if(key==='home')startTimer();
 }catch(error){if(id!==routeId)return;content.innerHTML=heading('Your workspace','Let’s reconnect.','Your saved records have not been changed.')+'<div class="desk-card">'+button('Try again','refresh')+'</div>';notice(error.message,true);}
}
async function renderHome(){
 const [summary,clock]=await Promise.all([api('/api/workforce/portal'),api('/api/workforce/shift')]);clockData=clock;
 const currentTime=new Intl.DateTimeFormat('en-GB',{timeZone:'Australia/Melbourne',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date());
 const entry=clock.entry,onBreak=Boolean(entry?.break_started_at),next=(summary.roster||[]).find(r=>r.shift_date>today()||(r.shift_date===today()&&r.end_time>currentTime));
 return heading('Your workday','Hello, '+esc(user.first_name)+'.','Your next shift, clocked hours and requests. All in one place.')+
 '<div class="desk-metrics">'+[['Completed today',hours(clock.today_seconds)+' h'],['Completed this week',hours(clock.week_seconds)+' h'],['Leave requests',(summary.leave||[]).filter(r=>r.status==='pending').length+' pending']].map(([label,value])=>'<div class="desk-metric"><span>'+label+'</span><strong>'+value+'</strong></div>').join('')+'</div>'+
 '<div class="desk-columns"><section class="desk-card desk-clock"><div class="eyebrow">'+(entry?(onBreak?'On a break':'Shift in progress'):'Ready when you are')+'</div><h2>'+ (entry?(onBreak?'Take a breather.':'You’re on the clock.'):'Start your workday.')+'</h2><div class="desk-clock-time" id="desk-clock-time" data-active="'+Boolean(entry)+'">'+(entry?'00:00:00':'Ready to start')+'</div><p>'+(entry?'Started '+esc(stamp(entry.clock_in))+' · '+esc(entry.location_name):'Choose your workplace and start when your shift begins.')+'</p>'+
 (!entry?select('Work location','clock_location',summary.locations.map(l=>[l.slug,l.name]),'wood-street'):'')+
 '<div class="desk-actions">'+(!entry?button('Start shift','clock','data-clock="in"','gold'):(onBreak?button('End break','clock','data-clock="break_end"'):button('Start unpaid break','clock','data-clock="break_start"'))+(entry?button('Finish shift','clock','data-clock="out"','gold'):''))+'</div>'+
 '<p class="desk-clock-note">'+(entry?'The timer shows elapsed time, including breaks. Completed work hours are calculated separately.':'No GPS or background location tracking. Clocking out submits the recorded hours for management review.')+'</p></section>'+
 '<div class="desk-stack"><section class="desk-card"><h2>Your next shift</h2>'+(next?'<span class="desk-chip">'+esc(dateLabel(next.shift_date))+'</span><h3 style="margin-top:18px">'+esc(timeLabel(next.start_time))+' – '+esc(timeLabel(next.end_time))+'</h3><p>'+esc(next.location_name)+'<br>'+esc(next.role_label)+'</p><a class="desk-button" data-variant="secondary" href="#roster">View my roster →</a>':empty('No published upcoming shifts yet. Management will publish your roster here.'))+'</section><section class="desk-card"><h2>Need some time off?</h2><p>Submit a leave request and attach a certificate if needed. Management reviews each request.</p><a class="desk-button" data-variant="secondary" href="#leave">Request time off →</a></section></div></div>';
}
function startTimer(){
 if(!clockData?.entry)return;const started=Date.parse(clockData.entry.clock_in),server=Date.parse(clockData.server_time),base=performance.now();
 const tick=()=>{const el=document.getElementById('desk-clock-time');if(!el)return;const seconds=Math.max(0,Math.floor((server-started+performance.now()-base)/1000));el.textContent=[Math.floor(seconds/3600),Math.floor(seconds/60)%60,seconds%60].map(n=>String(n).padStart(2,'0')).join(':');};tick();timer=setInterval(()=>{if(!document.hidden)tick();},1000);
}
async function renderRoster(){
 const end=addDays(weekStart,6);rosterData=await api((management?'/api/management/roster':'/api/workforce/roster')+'?start='+weekStart+'&end='+end);
 const days=Array.from({length:7},(_,i)=>addDays(weekStart,i));
 return heading(management?'Team planning':'Your published shifts',management?'A clear week ahead.':'My roster.',management?'Plan, review and publish shifts. Changes never alter the separate record of hours worked.':'Management publishes your shifts here. Your roster is read-only.',management?button('＋ Add a shift','shift-new','',''):'')+
 '<div class="desk-card"><div class="desk-calendar-controls"><div class="desk-date-nav">'+button('←','week-prev','aria-label="Previous week"')+'<strong>'+esc(dateLabel(weekStart))+' – '+esc(dateLabel(end))+'</strong>'+button('→','week-next','aria-label="Next week"')+'</div>'+button('This week','week-today')+'</div>'+
 '<div class="desk-calendar-wrap"><div class="desk-calendar">'+days.map(day=>'<section class="desk-day" data-today="'+String(day===today())+'"><div class="desk-day-heading">'+new Intl.DateTimeFormat('en-AU',{weekday:'short',timeZone:'UTC'}).format(new Date(day+'T12:00:00Z'))+'<strong>'+Number(day.slice(-2))+'</strong></div><div>'+((rosterData.roster||[]).filter(r=>r.shift_date===day).map(r=>'<'+(management?'button type="button" data-action="shift-edit" data-id="'+r.id+'"':'article')+' class="desk-shift" data-state="'+esc(r.status)+'"><strong>'+esc(timeLabel(r.start_time))+'–'+esc(timeLabel(r.end_time))+'</strong>'+(management?'<span>'+esc(nameOf(r))+'</span>':'')+'<span>'+esc(r.location_name)+'</span><small>'+esc(r.role_label)+' · '+esc(r.status)+'</small></'+(management?'button':'article')+'>').join('')||'<p class="desk-day-empty">No '+(management?'shifts':'published shifts')+'</p>')+'</div></section>').join('')+'</div></div>'+
 '<div class="desk-legend"><span><i class="desk-dot"></i> Published'+(management?' · visible to staff':'')+'</span>'+(management?'<span><i class="desk-dot draft"></i> Draft · management only</span>':'')+'</div></div>'+
 '<p class="desk-note">'+(management?'Publishing makes a shift visible to its assigned staff member. Resolve roster overlaps and approved leave before publishing.':'Need a change? Contact management or submit a time-off request. Clock in and out from My workday to record your actual hours.')+'</p>';
}
async function renderHours(){
 const result=await api('/api/workforce/report?period=weekly&on='+weekStart);
 return heading('Your recorded work','My hours.','Clocked work and breaks, with management review status. Planned roster hours are separate.')+
 '<div class="desk-calendar-controls"><div class="desk-date-nav">'+button('←','week-prev','aria-label="Previous week"')+'<strong>'+esc(dateLabel(result.start))+' – '+esc(dateLabel(result.end))+'</strong>'+button('→','week-next','aria-label="Next week"')+'</div>'+button('This week','week-today')+'</div>'+
 '<div class="desk-metrics">'+[['Recorded',result.totals.worked_seconds],['Approved',result.totals.approved_seconds],['Unpaid breaks',result.totals.unpaid_break_seconds]].map(([label,value])=>'<div class="desk-metric"><span>'+label+'</span><strong>'+hours(value)+' h</strong></div>').join('')+'</div><section class="desk-card"><h2>Completed work</h2>'+
 (result.rows.length?'<div class="desk-table-wrap"><table class="desk-table"><caption class="sr-only">My recorded hours for the selected week</caption><thead><tr><th>Date / location</th><th>Work</th><th>Breaks</th><th>Review</th></tr></thead><tbody>'+result.rows.map(r=>'<tr><td><strong>'+esc(dateLabel(r.date))+'</strong><small>'+esc(r.location)+'</small><small>'+esc(r.origin)+' · #'+r.entry_id+'</small></td><td>'+hours(r.worked_seconds)+' h<small>'+esc(stamp(r.clock_in))+'<br>'+esc(stamp(r.clock_out))+'</small></td><td>'+hours(r.unpaid_break_seconds)+' h unpaid<small>'+hours(r.paid_break_seconds)+' h paid</small></td><td>'+chip(r.status)+(r.review_comment?'<small>'+esc(r.review_comment)+'</small>':'')+'</td></tr>').join('')+'</tbody></table></div>':empty('No completed hours in this period. An open shift appears on My workday until you clock out.'))+'</section><p class="desk-note">If a clock entry needs correcting, contact management. Hours shown here do not calculate your pay, leave entitlement or award conditions.</p>';
}
async function renderLeave(){
 leaveData=await api(management?'/api/management/leave':'/api/workforce/leave');
 return heading('Time off',management?'Room for real life.':'Request time off.',management?'Review requests, check roster conflicts and keep decisions clear.':'Let management know the dates you need. A request is not approved leave until it is confirmed.',!management?button('＋ Request time off','leave-new','',''):'')+
 '<section class="desk-card"><h2>'+ (management?'Leave requests':'My requests')+'</h2>'+
 ((leaveData.requests||[]).length?'<div class="desk-table-wrap"><table class="desk-table"><caption class="sr-only">Leave requests and review status</caption><thead><tr>'+(management?'<th>Team member</th>':'')+'<th>Dates</th><th>Type</th><th>Status</th><th>Details</th></tr></thead><tbody>'+leaveData.requests.map(r=>'<tr>'+(management?'<td><strong>'+esc(nameOf(r))+'</strong></td>':'')+'<td>'+esc(dateLabel(r.start_date))+'<small>to '+esc(dateLabel(r.end_date))+'</small></td><td>'+esc(String(r.leave_type).replaceAll('_',' '))+'</td><td>'+chip(r.status)+(r.roster_conflicts?.length?'<small>'+r.roster_conflicts.length+' roster conflict(s)</small>':'')+'</td><td>'+button(management?'Review':'View','leave-view','data-id="'+r.id+'"')+'</td></tr>').join('')+'</tbody></table></div>':empty(management?'No leave requests to review.':'No time-off requests yet. Your requests and management decisions will appear here.'))+'</section>';
}
async function renderDocuments(){
 documentData=await api(management?'/api/management/documents':'/api/workforce/documents');
 return heading('Private documents',management?'The right records.':'My certificates.',management?'Review staff uploads. Medical documents stay private to their owner and management.':'Upload a medical certificate, professional qualification or other certificate for management review.',!management?button('＋ Upload a document','document-new','',''):'')+
 '<section class="desk-card"><h2>'+ (management?'Staff documents':'My uploaded documents')+'</h2>'+
 ((documentData.documents||[]).length?'<div class="desk-table-wrap"><table class="desk-table"><caption class="sr-only">Private staff documents</caption><thead><tr><th>Document'+(management?' / staff':'')+'</th><th>Coverage / expiry</th><th>Status</th><th>Details</th></tr></thead><tbody>'+documentData.documents.map(r=>'<tr><td><strong>'+esc(r.title)+'</strong><small>'+esc(r.category)+(management?' · '+esc(nameOf(r)):'')+'</small></td><td>'+(r.coverage_start?esc(dateLabel(r.coverage_start))+'<small>to '+esc(dateLabel(r.coverage_end))+'</small>':'Not specified')+(r.expiry_date?'<small>Expires '+esc(dateLabel(r.expiry_date))+'</small>':'')+'</td><td>'+chip(r.status)+'</td><td>'+button(management?'Review':'View','document-view','data-id="'+r.id+'"')+'</td></tr>').join('')+'</tbody></table></div>':empty('No documents uploaded yet.'))+'</section><p class="desk-note">PDF, JPG or PNG · maximum 5 MB. Upload only the certificate needed for the request. Do not include unrelated medical records or other people’s details.</p>';
}
async function renderProfile(){
 const result=await api('/api/account/profile'), p=result.profile||result;
 return heading('Your account','My details.','Keep your contact details up to date. Your role and permanent account number are managed by HV Swim.')+
 '<div class="desk-columns"><section class="desk-card"><h2>Contact details</h2><form class="desk-form" data-form="profile"><div class="desk-form-grid">'+field('First name','first_name','text',p.first_name,'required maxlength="80" autocomplete="given-name"')+field('Last name','last_name','text',p.last_name,'maxlength="80" autocomplete="family-name"')+'</div>'+field('Phone','phone','tel',p.phone,'maxlength="30" autocomplete="tel"')+'<div class="desk-form-footer"><button type="submit" class="desk-button">Save my details</button></div></form></section><section class="desk-card"><h2>Account identity</h2><dl class="desk-detail-list"><div><dt>Contact email</dt><dd>'+esc(p.email)+'</dd></div><div><dt>Staff number</dt><dd>'+esc(p.staff_number||user.staff_number||'Not assigned')+'</dd></div><div><dt>Access</dt><dd>'+ (management?'Management':'Staff self-service')+'</dd></div></dl><p class="desk-note">Contact management if your email or sign-in account needs to change. Matching an email alone does not link an existing profile.</p>'+button('Sign out other sessions','revoke-sessions')+'</section></div>';
}
function shiftDialog(row,trigger){
 if(row&&(row.status==='cancelled'||row.shift_date<today())){openDialog('Shift record',dateLabel(row.shift_date),chip(row.status)+'<p>'+esc(timeLabel(row.start_time))+' – '+esc(timeLabel(row.end_time))+'</p><p>'+esc(nameOf(row))+' · '+esc(row.location_name)+'</p><p>Past and cancelled shifts are preserved.</p>',trigger);return;}
 const r=row||{staff_id:'',location_slug:'wood-street',shift_date:weekStart<today()?today():weekStart,start_time:'09:00',end_time:'12:00',role_label:'Instructor',status:'draft'};
 const staff=[['','Choose a team member'],...(rosterData.staff||[]).map(p=>[p.id,nameOf(p)])];
 openDialog(row?'Edit shift':'Plan a shift','Drafts stay with management. Publish when the shift is ready for the assigned staff member.', '<form class="desk-form" data-form="shift" data-id="'+(r.id||'')+'" data-revision="'+(r.revision||0)+'">'+select('Team member','staff_id',staff,r.staff_id,'required')+'<div class="desk-form-grid">'+field('Shift date','shift_date','date',r.shift_date,'required')+select('Location','location_slug',(rosterData.locations||[]).map(l=>[l.slug,l.name]),r.location_slug,'required')+field('Start time','start_time','time',r.start_time,'required')+field('Finish time','end_time','time',r.end_time,'required')+'</div>'+field('Role / duty','role_label','text',r.role_label,'required maxlength="100"')+select('Visibility','status',[['draft','Draft — management only'],['published','Published — visible to staff']],r.status==='cancelled'?'draft':r.status)+'<div class="desk-actions"><button type="submit" class="desk-button">Save shift</button>'+(r.id&&r.status!=='cancelled'?button('Cancel shift','shift-cancel','data-id="'+r.id+'" data-revision="'+r.revision+'"'):'')+'</div></form>',trigger);
}
function leaveDialog(row,trigger){
 if(!row){openDialog('Request time off','Tell management the dates you need. Add a brief note only if it helps review the request.','<form class="desk-form" data-form="leave">'+select('Leave type','leave_type',[['annual','Annual leave'],['personal','Personal / sick leave'],['unpaid','Unpaid leave'],['other','Other time off']])+'<div class="desk-form-grid">'+field('First day','start_date','date',today(),'required')+field('Last day','end_date','date',today(),'required')+'</div><label class="desk-field"><span>Private note (optional)</span><textarea name="private_note" maxlength="1200" placeholder="Only details management needs to review this request"></textarea></label><button type="submit" class="desk-button">Submit request</button></form>',trigger);return;}
 openDialog(management?'Review time off':'My time-off request',dateLabel(row.start_date)+' to '+dateLabel(row.end_date),
 chip(row.status)+'<p class="desk-note">'+esc(row.private_note||'No private note supplied.')+'</p>'+
 (row.roster_conflicts?.length?'<p class="desk-note">Published roster shifts overlap these dates. Resolve the shifts before approving leave.</p>':'')+
 (row.review_note?'<p class="desk-note">Management: '+esc(row.review_note)+'</p>':'')+
 (management&&row.staff_id!==user.id&&['pending','approved'].includes(row.status)?'<form class="desk-form" data-form="leave-review" data-id="'+row.id+'" data-revision="'+row.revision+'">'+select('Decision','status',row.status==='approved'?[['cancelled','Withdraw approval']]:[['approved','Approve'],['declined','Decline']],'approved')+'<label class="desk-field"><span>Review note</span><textarea name="review_note" maxlength="1000" required></textarea></label><button type="submit" class="desk-button">Save decision</button></form>':(!management&&row.status==='pending'?button('Cancel my request','leave-cancel','data-id="'+row.id+'" data-revision="'+row.revision+'"'):'')),trigger);
}
async function documentDialog(row,trigger){
 if(row){
 const url=/^\/api\/(?:workforce|management)\/documents\/\d+\/download$/.test(row.download_url||'')?row.download_url:'';
 openDialog(row.title,management?nameOf(row)+' · '+row.category:'Your private '+row.category+' document',chip(row.status)+'<p class="desk-note">'+esc(row.original_filename)+' · '+(row.byte_count/1000000).toFixed(2)+' MB</p>'+
 (url?'<a class="desk-button" data-variant="secondary" href="'+esc(url)+'" download>Download certificate ↓</a>':'')+
 (row.review_note?'<p class="desk-note">Management: '+esc(row.review_note)+'</p>':'')+
 (management&&row.staff_id!==user.id&&row.status==='pending'?'<form class="desk-form" data-form="document-review" data-id="'+row.id+'" data-revision="'+row.revision+'">'+select('Review result','status',[['accepted','Accept certificate'],['rejected','Request a replacement']])+'<label class="desk-field"><span>Review note</span><textarea name="review_note" maxlength="1000" required></textarea></label><button type="submit" class="desk-button">Save review</button></form>':''),trigger);return;
 }
 const leave=await api('/api/workforce/leave');
 openDialog('Upload a certificate','PDF, JPG or PNG, up to 5 MB. Your file will be encrypted and visible only to you and management.','<form class="desk-form" data-form="document">'+select('Document type','category',[['medical','Medical certificate'],['professional','Professional qualification'],['other','Other certificate']])+field('Document title','title','text','','required minlength="2" maxlength="120" placeholder="For example, medical certificate"')+'<label class="desk-field"><span>Certificate file</span><input name="document" type="file" accept="application/pdf,image/jpeg,image/png" required></label><div class="desk-form-grid">'+field('Covers from (optional)','coverage_start','date')+field('Covers until (optional)','coverage_end','date')+field('Expiry date (if applicable)','expiry_date','date')+'</div>'+select('Link to a leave request (optional)','leave_request_id',[['','No linked request'],...(leave.requests||[]).map(r=>[r.id,dateLabel(r.start_date)+' – '+dateLabel(r.end_date)])])+'<button type="submit" class="desk-button">Upload for review</button></form>',trigger);
}

let noticeData=[];
async function renderAvailability(){
 const result=await api(management?'/api/management/shift-notices':'/api/workforce/shift-notices');noticeData=result.notices;
 return heading('Absence & availability',management?'Keep the team informed.':'Can’t work a shift?',management?'Review absence and availability notices. Arrange cover and update the roster separately.':'Tell management if you are absent or unable to work an assigned shift. Call 0413 462 112 for an urgent change.',management?'':button('Report a shift issue','notice-new','',''))+
 '<section class="desk-card"><h2>'+ (management?'Staff shift notices':'My shift notices')+'</h2>'+ (noticeData.map(r=>'<article class="desk-card"><h3>'+esc(dateLabel(r.shift_date))+' · '+esc(timeLabel(r.start_time))+'</h3><p>'+esc(r.location_name)+(management?' · '+esc(nameOf(r)):'')+'</p>'+chip(r.status)+'<p>'+esc(r.kind==='absent'?'Absent from shift':'Unable to work shift')+'</p>'+button('View notice','notice-view','data-id="'+r.id+'"')+'</article>').join('')||empty('No shift notices.'))+'</section><p class="desk-note">Sending a notice does not change your roster, calculate pay or approve leave. Management confirms the next steps. Detailed medical information belongs in your private certificate upload.</p>';
}
async function noticeDialog(row,trigger){
 if(row){openDialog('Shift notice',dateLabel(row.shift_date)+' · '+timeLabel(row.start_time),chip(row.status)+'<p>'+esc(row.private_note||'No note supplied.')+'</p><p>'+esc(row.review_note||'Awaiting management review.')+'</p>'+(management&&row.staff_id!==user.id&&row.status!=='resolved'?'<form class="desk-form" data-form="notice-review" data-id="'+row.id+'" data-revision="'+row.revision+'">'+select('Response','status',[['acknowledged','Acknowledge'],['resolved','Mark resolved']])+'<label class="desk-field"><span>Next steps / response</span><textarea name="review_note" required minlength="3" maxlength="1200"></textarea></label><button type="submit" class="desk-button">Save response</button></form>':''),trigger);return;}
 const roster=await api('/api/workforce/roster?start='+addDays(today(),-7)+'&end='+addDays(today(),90));
 if(!roster.roster.length){notice('No published shifts in this period. Contact management to discuss availability.');return;}
 openDialog('Report a shift issue','For an urgent change, call management on 0413 462 112 as well.','<form class="desk-form" data-form="notice">'+select('Your assigned shift','roster_id',roster.roster.map(r=>[r.id,dateLabel(r.shift_date)+' · '+timeLabel(r.start_time)+' · '+r.location_name]),'','required')+select('What do you need to report?','kind',[['unavailable','I cannot work this shift'],['absent','I am absent from this shift']])+'<label class="desk-field"><span>Brief private note (optional)</span><textarea name="private_note" maxlength="1200"></textarea></label><button type="submit" class="desk-button">Send to management</button></form>',trigger);
}
function fileData(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(new Error('The file could not be read.'));reader.readAsDataURL(file);});}
async function action(buttonEl){
 const actionName=buttonEl.dataset.action,id=Number(buttonEl.dataset.id);
 if(actionName==='refresh')return render();
 if(actionName==='week-prev'||actionName==='week-next'||actionName==='week-today'){weekStart=actionName==='week-today'?monday(today()):addDays(weekStart,actionName==='week-next'?7:-7);return render();}
 if(actionName==='shift-new')return shiftDialog(null,buttonEl);
 if(actionName==='shift-edit')return shiftDialog(rosterData.roster.find(r=>r.id===id),buttonEl);
 if(actionName==='notice-new')return noticeDialog(null,buttonEl);
 if(actionName==='notice-view')return noticeDialog(noticeData.find(r=>r.id===id),buttonEl);
 if(actionName==='leave-new')return leaveDialog(null,buttonEl);
 if(actionName==='leave-view')return leaveDialog(leaveData.requests.find(r=>r.id===id),buttonEl);
 if(actionName==='document-new')return documentDialog(null,buttonEl);
 if(actionName==='document-view')return documentDialog(documentData.documents.find(r=>r.id===id),buttonEl);
 if(busy)return;busy=true;buttonEl.disabled=true;
 const target=dialog.open?dialog.querySelector('[data-dialog-feedback]'):feedback;
 try{
  if(actionName==='clock'){
   const a=buttonEl.dataset.clock,entry=clockData?.entry,key=a+':'+(entry?.id||'new');
   if(!clockRequest||clockRequest.key!==key)clockRequest={key,payload:{action:a,request_id:crypto.randomUUID(),location_slug:content.querySelector('[name=clock_location]')?.value||'wood-street',...(entry?{entry_id:entry.id}:{}),paid_break:false}};
   await post('/api/workforce/clock',clockRequest.payload);clockRequest=null;await render();notice(a==='out'?'Clocked out. Your hours were submitted for review.':'Your workday has been updated.');
  } else if(actionName==='shift-cancel'){await post('/api/management/roster/'+id+'/cancel',{revision:Number(buttonEl.dataset.revision)});closeDialog();await render();notice('Shift cancelled. The actual hours record is unchanged.');}
  else if(actionName==='leave-cancel'){await post('/api/workforce/leave/'+id+'/cancel',{revision:Number(buttonEl.dataset.revision)});closeDialog();await render();notice('Your leave request was cancelled.');}
  else if(actionName==='revoke-sessions'){await post('/api/account/revoke-other-sessions',{});notice('Other sessions have been signed out.');}
 }catch(error){notice(error.message,true,target);}finally{busy=false;buttonEl.disabled=false;}
}
document.addEventListener('click',event=>{const control=event.target.closest('[data-action]');if(control)action(control).catch(error=>notice(error.message,true));});
document.addEventListener('submit',async event=>{
 const form=event.target.closest('[data-form]');if(!form)return;event.preventDefault();if(busy)return;
 busy=true;const submit=form.querySelector('button[type=submit],button:not([type])');if(submit)submit.disabled=true;
 const target=dialog.open?dialog.querySelector('[data-dialog-feedback]'):feedback;
 try{
  const data=Object.fromEntries(new FormData(form)),kind=form.dataset.form,id=Number(form.dataset.id),revision=Number(form.dataset.revision);
  if(kind==='profile'){await api('/api/account/profile',{method:'PATCH',body:JSON.stringify(data)});user.first_name=data.first_name;user.last_name=data.last_name;document.getElementById('desk-person-name').textContent=nameOf(user);}
  if(kind==='shift'){data.staff_id=Number(data.staff_id);if(id)data.revision=revision;await api('/api/management/roster'+(id?'/'+id:''),{method:id?'PATCH':'POST',body:JSON.stringify(data)});}
  if(kind==='notice'){data.roster_id=Number(data.roster_id);await post('/api/workforce/shift-notices',data);}
  if(kind==='notice-review')await post('/api/management/shift-notices/'+id+'/review',{...data,revision});
  if(kind==='leave')await post('/api/workforce/leave',data);
  if(kind==='leave-review')await post('/api/management/leave/'+id+'/decision',{...data,revision});
  if(kind==='document-review')await post('/api/management/documents/'+id+'/review',{...data,revision});
  if(kind==='document'){
   const file=data.document;if(!file||file.size===0)throw new Error('Choose a certificate file.');
   if(file.size>5000000)throw new Error('Choose a file no larger than 5 MB.');
   if(!['application/pdf','image/jpeg','image/png'].includes(file.type))throw new Error('Choose a PDF, JPG or PNG file.');
   delete data.document;data.document_base64=await fileData(file);data.document_media_type=file.type;data.original_filename=file.name;
   for(const key of ['coverage_start','coverage_end','expiry_date','leave_request_id'])if(!data[key])delete data[key];
   if(data.leave_request_id)data.leave_request_id=Number(data.leave_request_id);
   await post('/api/workforce/documents',data);
  }
  if(dialog.open)closeDialog();await render();notice(kind==='document'?'Document uploaded securely and awaiting management review.':kind==='leave'?'Request submitted. Management will review it.':'Saved successfully.');
 }catch(error){notice(error.message,true,target);}finally{busy=false;if(submit)submit.disabled=false;}
});
document.getElementById('desk-logout').addEventListener('click',async event=>{const control=event.currentTarget;control.disabled=true;try{await post('/api/auth/logout',{});location.href='login.html';}catch(error){notice(error.message,true);control.disabled=false;}});
window.addEventListener('hashchange',render);
(async()=>{
 try{
  const auth=await api('/api/auth/me');user=auth.user;csrf=auth.csrf_token;
  if(!user||user.role!==expectedRole){location.href=user?.role==='staff'?'staff.html':user?.role==='admin'?'admin.html':'customer.html';return;}
  document.getElementById('desk-person-name').textContent=nameOf(user);
  document.getElementById('desk-avatar').textContent=(user.first_name?.[0]||'H')+(user.last_name?.[0]||'V');
  document.getElementById('desk-logout').disabled=false;nav();await render();
 }catch(error){content.innerHTML=heading('Your workspace','Unable to connect.','Sign in again or retry when the connection returns.')+'<a class="desk-button" href="login.html">Go to sign in</a>';notice(error.message,true);}
})();
})();