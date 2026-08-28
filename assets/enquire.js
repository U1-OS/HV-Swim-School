(() => {
  'use strict';
  const form=document.getElementById('enrolment-wizard');
  if(!form)return;

  const days=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
  const esc=value=>String(value??'').replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const money=value=>new Intl.NumberFormat('en-AU',{style:'currency',currency:'AUD'}).format(Number(value||0));
  const incoming=new URLSearchParams(location.search);
  const queryProgram=incoming.get('program')||'';
  const queryClass=incoming.get('class')||'';
  const merchInterest=incoming.get('merch')||'';
  let currentStep=1;
  let classes=[];

  const elements={
    back:document.getElementById('wizard-back'),next:document.getElementById('wizard-next'),submit:document.getElementById('wizard-submit'),
    error:document.getElementById('wizard-error'),stepLabel:document.getElementById('wizard-step-label'),progressBar:document.getElementById('wizard-progress-bar'),
    swimmerName:document.getElementById('swimmer-name'),age:document.getElementById('swimmer-age'),goal:document.getElementById('swimmer-goal'),program:document.getElementById('program-interest'),
    preferredClass:document.getElementById('preferred-class'),preferredDays:document.getElementById('preferred-days'),experience:document.getElementById('experience-summary'),notes:document.getElementById('experience-notes')
  };

  function stepElement(step){return document.querySelector(`[data-step="${step}"]`);}
  function validateStep(step){
    const section=stepElement(step);
    for(const input of section.querySelectorAll('[required]')){
      if(!input.checkValidity()){
        elements.error.textContent=input.type==='radio'?'Choose the option that feels closest before continuing.':'Please complete the highlighted field before continuing.';
        input.focus({preventScroll:true});
        input.scrollIntoView({behavior:'smooth',block:'center'});
        return false;
      }
    }
    elements.error.textContent='';return true;
  }
  function showStep(step,scroll=true){
    currentStep=Math.max(1,Math.min(4,step));
    document.querySelectorAll('.wizard-step').forEach(section=>{const active=Number(section.dataset.step)===currentStep;section.hidden=!active;section.classList.toggle('active',active);});
    document.querySelectorAll('[data-progress]').forEach(item=>{const value=Number(item.dataset.progress);item.classList.toggle('active',value===currentStep);item.classList.toggle('complete',value<currentStep);});
    elements.stepLabel.textContent=`Step ${currentStep} of 4`;
    elements.progressBar.style.width=`${currentStep*25}%`;
    elements.back.hidden=currentStep===1;
    elements.next.hidden=currentStep===4;
    elements.submit.hidden=currentStep!==4;
    elements.error.textContent='';
    if(currentStep===4)renderReview();
    if(scroll)document.getElementById('enrolment').scrollIntoView({behavior:'smooth',block:'start'});
  }

  function recommendation(){
    const age=elements.age.value;
    const confidence=form.querySelector('[name="confidence"]:checked')?.value||'';
    const goal=elements.goal.value;
    let title='Learn to Swim';
    let copy='A small-group pathway can build water confidence and strong core swimming skills, with the exact level confirmed personally.';
    if(age.includes('4–12')||age==='1–2 years'){title='Infant Aquatics';copy='A carer-supported infant pathway can build positive early water experiences and safe foundations.';}
    else if(goal==='personal'||confidence.includes('one-to-one')){title='Private 1:1 Lesson';copy='One-to-one coaching can match the swimmer’s pace, confidence, communication preferences and individual goals.';}
    else if(goal==='technique'||confidence==='Swimming independently'){title='Stroke Development';copy='A technique-focused pathway can strengthen movement patterns, breathing and endurance for an independent swimmer.';}
    else if((age==='Teen'||age==='Adult')&&confidence.includes('New')){title='Adult / Teen Private Assessment';copy='A calm private assessment offers a personal, no-pressure starting point for a teen or adult.';}
    if(queryProgram&&!confidence&&!goal){title=queryProgram;copy='You arrived with this program selected. Answer the questions so the team can confirm whether it is the right starting point.';}
    elements.program.value=title;
    const result=document.getElementById('pathway-recommendation');
    result.innerHTML=`<span>Suggested pathway</span><strong>${esc(title)}</strong><p>${esc(copy)} <a href="programs.html">Compare program details →</a></p>`;
    result.classList.add('ready');
    filterClasses();
  }

  function classGroup(title){const value=String(title||'').toLowerCase();if(value.includes('infant'))return'infant';if(value.includes('private'))return'private';if(value.includes('stroke'))return'stroke';return'learn';}
  function programGroup(){return classGroup(elements.program.value);}
  function renderClasses(){
    const target=document.getElementById('wizard-class-grid');
    const group=programGroup();
    const sorted=[...classes].sort((a,b)=>Number(classGroup(a.title)!==group)-Number(classGroup(b.title)!==group));
    target.innerHTML=`<label class="wizard-class-card flexible"><input type="radio" name="class_choice" value="Flexible—team recommendation"><span class="class-choice-check">✓</span><div><span class="class-match-label">Best fit</span><strong>Keep me flexible</strong><small>Let HV Swim recommend the program, class and time.</small></div></label>`+sorted.map(item=>{
      const available=Number(item.available||0);
      const value=`${item.title} · ${days[item.weekday]} ${item.start_time} · ${item.location_name}`;
      const isMatch=classGroup(item.title)===group;
      const selected=queryClass&&value.toLowerCase().includes(queryClass.toLowerCase().replace(' at ',' · '));
      return `<label class="wizard-class-card ${isMatch?'recommended':''}"><input type="radio" name="class_choice" value="${esc(value)}" ${selected?'checked':''}><span class="class-choice-check">✓</span><div><span class="class-match-label">${isMatch?'Suggested match':'Other pathway'}</span><strong>${esc(item.title)}</strong><small>${esc(days[item.weekday])} · ${esc(item.start_time)} · ${esc(item.location_name)}</small><p><b>${money(item.price)} preview</b><em class="${available?'available':'waitlist'}">${available?`${available} ${available===1?'place':'places'} showing`:'Waitlist'}</em></p></div></label>`;
    }).join('');
    const selected=target.querySelector('[name="class_choice"]:checked');
    if(selected)elements.preferredClass.value=selected.value;
  }
  function filterClasses(){if(classes.length)renderClasses();}
  document.getElementById('wizard-class-grid').addEventListener('change',event=>{if(event.target.name==='class_choice')elements.preferredClass.value=event.target.value;});
  document.querySelector('.day-choice-grid').addEventListener('change',()=>{elements.preferredDays.value=[...form.querySelectorAll('[name="preferred_day"]:checked')].map(input=>input.value).join(', ');});

  function renderReview(){
    if(merchInterest){
      document.getElementById('enrolment-review').innerHTML=`<div><span>Enquiry type</span><strong>HV Swim Collection</strong><small>Pre-launch merchandise interest</small></div><div><span>Saved preferences</span><strong>${esc(merchInterest)}</strong><small>No stock is reserved and no payment is taken</small></div><div><span>Next step</span><strong>Team follow-up</strong><small>Final products, options and launch timing are confirmed personally</small></div>`;
      return;
    }
    const confidence=form.querySelector('[name="confidence"]:checked')?.value||'Not supplied';
    const goal=elements.goal.selectedOptions[0]?.textContent||'Not supplied';
    document.getElementById('enrolment-review').innerHTML=`<div><span>Swimmer</span><strong>${esc(elements.swimmerName.value||'Merchandise enquiry')}</strong><small>${esc(elements.age.value||'Not applicable')}</small></div><div><span>Suggested pathway</span><strong>${esc(elements.program.value||'Team recommendation')}</strong><small>${esc(confidence)} · ${esc(goal)}</small></div><div><span>Class preference</span><strong>${esc(elements.preferredClass.value||'Flexible')}</strong><small>${esc(elements.preferredDays.value||'No other days selected')}</small></div>`;
  }
  function composeExperience(){
    if(merchInterest)return `Merchandise collection interest: ${merchInterest}`;
    const confidence=form.querySelector('[name="confidence"]:checked')?.value||'Not supplied';
    const goal=elements.goal.selectedOptions[0]?.textContent||'Not supplied';
    return `Confidence: ${confidence}. Main goal: ${goal}.${elements.notes.value.trim()?` Additional context: ${elements.notes.value.trim()}`:''}`;
  }

  elements.next.addEventListener('click',()=>{if(validateStep(currentStep)){if(currentStep===2)recommendation();showStep(currentStep+1);}});
  elements.back.addEventListener('click',()=>showStep(currentStep-1));
  form.addEventListener('change',event=>{if(['confidence','swimmer-goal'].includes(event.target.name)||event.target.id==='swimmer-goal')recommendation();});
  form.addEventListener('submit',async event=>{
    event.preventDefault();
    if(!validateStep(4))return;
    elements.experience.value=composeExperience();
    elements.preferredDays.value=[...form.querySelectorAll('[name="preferred_day"]:checked')].map(input=>input.value).join(', ');
    const payload=Object.fromEntries(new FormData(form).entries());
    delete payload.confidence;delete payload.class_choice;delete payload.preferred_day;
    elements.submit.disabled=true;elements.submit.textContent='Sending securely…';elements.error.textContent='';
    try{
      const response=await fetch('/api/public/enquiries',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const result=await response.json();if(!response.ok)throw new Error(result.detail||'The enquiry could not be sent.');
      form.hidden=true;document.querySelector('.enrolment-progress').hidden=true;
      document.getElementById('success-reference').textContent=result.reference||`HV-ENQ-${String(result.id).padStart(4,'0')}`;
      document.getElementById('enrolment-success').hidden=false;
      document.getElementById('enrolment-success').scrollIntoView({behavior:'smooth',block:'center'});
    }catch(problem){elements.error.textContent=`${problem.message} Please try again or call 0413 462 112.`;elements.submit.disabled=false;elements.submit.innerHTML='Send secure enquiry <span aria-hidden="true">→</span>';}
  });

  fetch('/api/classes',{headers:{Accept:'application/json'}}).then(async response=>{const payload=await response.json();if(!response.ok)throw new Error();classes=payload.classes||[];renderClasses();}).catch(()=>{document.getElementById('wizard-class-grid').innerHTML='<div class="empty-state"><strong>We cannot show class times at the moment.</strong><p>Keep going anyway — choose &ldquo;flexible&rdquo; below and the team will confirm the current options when they reply.</p></div>';});

  if(queryProgram){elements.program.value=queryProgram;document.getElementById('pathway-recommendation').innerHTML=`<span>Selected pathway</span><strong>${esc(queryProgram)}</strong><p>Complete the confidence questions so the team can confirm this starting point.</p>`;}
  if(merchInterest){
    elements.swimmerName.value='Merchandise enquiry';elements.age.value='Adult';elements.program.value='HV Swim Collection';elements.preferredClass.value='Not applicable';elements.notes.value=merchInterest;
    document.querySelector('.enrolment-hero h1').innerHTML='Your collection <span>interest is ready.</span>';
    document.querySelector('.enrolment-hero-grid > div > p').textContent='Add your contact details and send the saved merchandise preferences directly to the HV Swim team before the collection launches.';
    showStep(4,false);
  }else showStep(1,false);
})();
