(() => {
  'use strict';
  const form=document.getElementById('enrolment-wizard');
  if(!form)return;

  const days=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
  const esc=value=>String(value??'').replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const money=value=>new Intl.NumberFormat('en-AU',{style:'currency',currency:'AUD'}).format(Number(value||0));
  const classTime=window.HVSwim?.formatClassTime||(value=>String(value||''));
  const request=window.HVSwim?.fetchJSON||(async(url,options={})=>{const response=await fetch(url,options);const payload=await response.json();if(!response.ok)throw new Error(payload.detail||'Request unavailable');return payload;});
  const incoming=new URLSearchParams(location.search);
  const queryProgram=incoming.get('program')||'';
  const queryClass=incoming.get('class')||'';
  const knownLocations=['Wood Street Indoor Pool','Bendigo East Swimming Pool'];
  const queryLocation=knownLocations.find(item=>item===incoming.get('location'))||'';
  const merchInterest=incoming.get('merch')||'';
  const matcherConfidence=incoming.get('matcher_confidence')||'';
  const matcherGoal=incoming.get('matcher_goal')||'';
  const termWeeks=incoming.get('term_weeks')||'';
  const lessonFormat=incoming.get('lesson_format')||'';
  const enquiryType=document.getElementById('enquiry-type');
  const heroHeading=document.querySelector('.enrolment-hero h1');
  const heroCopy=document.querySelector('.enrolment-hero-grid > div > p');
  const lessonHeading=heroHeading.innerHTML;
  const lessonCopy=heroCopy.textContent;
  const contactCopyTargets=[
    ['.enrolment-hero .btn-primary','Write your message →'],
    ['.enrolment-hero-card ol','<li><span>01</span><p><strong>Your message is saved</strong><small>A reference number confirms the enquiry was received.</small></p></li><li><span>02</span><p><strong>The team reviews it</strong><small>Your question goes to the right people at HV Swim.</small></p></li><li><span>03</span><p><strong>We follow up personally</strong><small>The team uses your preferred contact method.</small></p></li>'],
    ['[data-step="4"] .wizard-heading > span','Your details · Review &amp; send'],
    ['[data-step="4"] .wizard-heading > p','Add your message and the contact details the team should use.'],
    ['[data-step="4"] .info-note','<strong>What happens next:</strong> Your enquiry is saved for the HV Swim team to review and follow up. This form does not take payment or change a booking. See the <a href="privacy.html">privacy policy</a> for how your details are handled.'],
    ['#enrolment-success > p','Your enquiry has been received. Keep your reference number; the team will review your message and follow up using your preferred contact method.'],
    ['#enrolment-success .success-next','<div><strong>1</strong><span>Your message is saved</span></div><div><strong>2</strong><span>The team reviews your question</span></div><div><strong>3</strong><span>We follow up personally</span></div>']
  ].map(([selector,contact])=>{const element=document.querySelector(selector);return {element,contact,lesson:element?.innerHTML};});
  const lessonEnquiry=()=>['lesson','lesson_question','private_lesson'].includes(enquiryType.value);
  const scrollBehavior=()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth';
  const DRAFT_KEY='hv-swim-enquiry-preferences-v1';
  let currentStep=1;
  let classes=[];

  const elements={
    back:document.getElementById('wizard-back'),next:document.getElementById('wizard-next'),submit:document.getElementById('wizard-submit'),
    error:document.getElementById('wizard-error'),stepLabel:document.getElementById('wizard-step-label'),progressBar:document.getElementById('wizard-progress-bar'),progressTrack:document.getElementById('wizard-progress-track'),
    swimmerName:document.getElementById('swimmer-name'),age:document.getElementById('swimmer-age'),goal:document.getElementById('swimmer-goal'),program:document.getElementById('program-interest'),
    preferredClass:document.getElementById('preferred-class'),preferredDays:document.getElementById('preferred-days'),experience:document.getElementById('experience-summary'),notes:document.getElementById('experience-notes'),
    phone:document.getElementById('contact-phone'),contactMethod:document.getElementById('contact-method')
  };

  function readDraft(){
    try{return JSON.parse(sessionStorage.getItem(DRAFT_KEY)||'null');}catch(_){return null;}
  }
  function saveDraft(){
    if(!lessonEnquiry())return;
    const draft={
      age:elements.age.value,
      confidence:form.querySelector('[name="confidence"]:checked')?.value||'',
      goal:elements.goal.value,
      program:elements.program.value,
      preferredClass:elements.preferredClass.value,
      preferredDays:[...form.querySelectorAll('[name="preferred_day"]:checked')].map(input=>input.value),
      savedAt:Date.now()
    };
    try{sessionStorage.setItem(DRAFT_KEY,JSON.stringify(draft));}catch(_){}
  }
  function clearDraft(){try{sessionStorage.removeItem(DRAFT_KEY);}catch(_){}}

  function stepElement(step){return document.querySelector(`[data-step="${step}"]`);}
  function fieldLabel(input){
    const byFor=input.id&&document.querySelector(`label[for="${input.id}"]`);
    if(byFor)return byFor.textContent.trim().replace(/\s+/g,' ');
    const group=input.closest('fieldset');
    const legend=group&&group.querySelector('legend');
    return legend?legend.textContent.trim().replace(/\s+/g,' '):'';
  }
  function describeWizardError(input,invalid){
    const extra='wizard-error';
    const described=(input.getAttribute('aria-describedby')||'').split(/\s+/).filter(Boolean).filter(id=>id!==extra);
    if(invalid) input.setAttribute('aria-describedby',[...described,extra].join(' '));
    else if(described.length) input.setAttribute('aria-describedby',described.join(' '));
    else input.removeAttribute('aria-describedby');
  }
  function markInvalid(input,invalid){
    const target=input.type==='radio'?(input.closest('fieldset')||input):input;
    target.classList.toggle('field-invalid',invalid);
    input.setAttribute('aria-invalid',invalid?'true':'false');
    describeWizardError(input,invalid);
    if(invalid&&!input.dataset.revalidateBound){
      input.dataset.revalidateBound='1';
      const clear=()=>{ if(input.checkValidity()){markInvalid(input,false);elements.error.textContent='';} };
      input.addEventListener('input',clear); input.addEventListener('change',clear);
    }
  }
  function syncPhoneRequirement(){
    const required=['phone','sms'].includes(elements.contactMethod.value);
    elements.phone.required=required;
    elements.phone.setAttribute('aria-required',String(required));
    const hint=document.getElementById('phone-hint');
    if(hint)hint.textContent=required?'Required for your selected reply method.':'Optional when email is selected.';
    if(!required)markInvalid(elements.phone,false);
  }
  function validateStep(step){
    if(step===4)syncPhoneRequirement();
    const section=stepElement(step);
    section.querySelectorAll('[required]').forEach(input=>markInvalid(input,false));
    for(const input of section.querySelectorAll('input:not([type="hidden"]),select,textarea')){
      if(input.disabled)continue;
      if(input.type!=='checkbox'&&input.type!=='radio')input.value=input.value.trim();
      if(!input.checkValidity()){
        const name=fieldLabel(input);
        if(input.type==='radio')elements.error.textContent=name?`Choose an option for “${name}” before continuing.`:'Choose the option that feels closest before continuing.';
        else if(input.validity.typeMismatch&&input.type==='email')elements.error.textContent='Enter a complete email address, such as name@example.com.';
        else if(input===elements.phone&&input.validity.valueMissing)elements.error.textContent='Enter a phone number for the reply method you selected.';
        else if(input===elements.phone&&input.validity.patternMismatch)elements.error.textContent='Enter a complete phone number using numbers, spaces, brackets or +.';
        else elements.error.textContent=name?`Please fill in “${name}” before continuing.`:'Please complete the highlighted field before continuing.';
        markInvalid(input,true);
        input.focus({preventScroll:true});
        input.scrollIntoView({behavior:scrollBehavior(),block:'center'});
        return false;
      }
    }
    elements.error.textContent='';return true;
  }
  function showStep(step,scroll=true){
    const next=Math.max(1,Math.min(4,step));
    const reduced=document.documentElement.dataset.motion==='off'||window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    form.dataset.stepDir=next<currentStep?'back':'forward';
    currentStep=next;
    form.dataset.currentStep=String(currentStep);
    document.querySelectorAll('.wizard-step').forEach(section=>{
      const active=Number(section.dataset.step)===currentStep;
      section.hidden=!active;
      section.classList.remove('active');
      if(active){
        if(!reduced) void section.offsetWidth;
        section.classList.add('active');
      }
    });
    document.querySelectorAll('[data-progress]').forEach(item=>{const value=Number(item.dataset.progress);item.classList.toggle('active',value===currentStep);item.classList.toggle('complete',value<currentStep);if(value===currentStep)item.setAttribute('aria-current','step');else item.removeAttribute('aria-current');});
    elements.stepLabel.textContent=`Step ${currentStep} of 4`;
    elements.progressBar.style.width=`${currentStep*25}%`;
    elements.progressTrack?.setAttribute('aria-valuenow',String(currentStep));
    elements.progressTrack?.setAttribute('aria-valuetext',`Step ${currentStep} of 4`);
    elements.back.hidden=currentStep===1||!lessonEnquiry();
    elements.next.hidden=currentStep===4;
    elements.submit.hidden=currentStep!==4;
    elements.error.textContent='';
    if(currentStep===4)renderReview();
    if(scroll){
      document.getElementById('enrolment').scrollIntoView({behavior:scrollBehavior(),block:'start'});
      requestAnimationFrame(()=>{
        const heading=stepElement(currentStep).querySelector('h2');
        heading?.focus({preventScroll:true});
      });
    }
  }

  function recommendation(){
    const age=elements.age.value;
    const confidence=form.querySelector('[name="confidence"]:checked')?.value||'';
    const goal=elements.goal.value;
    let {title, explanation:copy}=window.HVLessonPathway({age,confidence,goal});
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
    const locationMatch=item=>Boolean(queryLocation&&String(item.location_name||'')===queryLocation);
    const sorted=[...classes].sort((a,b)=>{
      const programScore=Number(classGroup(a.title)!==group)-Number(classGroup(b.title)!==group);
      if(programScore)return programScore;
      return Number(!locationMatch(a))-Number(!locationMatch(b));
    });
    target.innerHTML=`<label class="wizard-class-card flexible"><input type="radio" name="class_choice" value="Flexible—team recommendation"><span class="class-choice-check">✓</span><div><span class="class-match-label">Best fit</span><strong>Keep me flexible</strong><small>Let HV Swim recommend the program, class and time.</small></div></label>`+sorted.map(item=>{
      const available=Number(item.available||0);
      const time=classTime(item.start_time);
      const value=`${item.title} · ${days[item.weekday]} ${time} · ${item.location_name}`;
      const isMatch=classGroup(item.title)===group;
      const selected=(queryClass&&value.toLowerCase().includes(queryClass.toLowerCase().replace(' at ',' · ')))||(!queryClass&&elements.preferredClass.value===value);
      const preferredVenue=locationMatch(item);
      const matchLabel=isMatch&&preferredVenue?'Program + venue match':(preferredVenue?'Preferred venue':(isMatch?'Suggested match':'Other pathway'));
      return `<label class="wizard-class-card ${isMatch?'recommended':''}"><input type="radio" name="class_choice" value="${esc(value)}" ${selected?'checked':''}><span class="class-choice-check">✓</span><div><span class="class-match-label">${matchLabel}</span><strong>${esc(item.title)}</strong><small>${esc(days[item.weekday])} · ${esc(time)} · ${esc(item.location_name)}</small><p><b>${/private/i.test(item.title)?'Private pricing by enquiry':`${money(item.price)} indicative`}</b><em class="${available?'available':'waitlist'}">${available?`${available} ${available===1?'place':'places'} showing`:'Waitlist'}</em></p></div></label>`;
    }).join('');
    const selected=target.querySelector('[name="class_choice"]:checked');
    if(selected)elements.preferredClass.value=selected.value;
    else if(queryLocation)elements.preferredClass.value=`Location preference: ${queryLocation}`;
  }
  function filterClasses(){if(classes.length)renderClasses();}
  document.getElementById('wizard-class-grid').addEventListener('change',event=>{if(event.target.name==='class_choice'){elements.preferredClass.value=event.target.value;saveDraft();}});
  document.querySelector('.day-choice-grid').addEventListener('change',()=>{elements.preferredDays.value=[...form.querySelectorAll('[name="preferred_day"]:checked')].map(input=>input.value).join(', ');saveDraft();});

  function renderReview(){
    if(!lessonEnquiry()){
      document.getElementById('enrolment-review').innerHTML=`<div><span>Enquiry type</span><strong>${esc(enquiryType.selectedOptions[0].textContent)}</strong><small>The team will review your message and reply using your preferred contact method.</small></div>`;
      return;
    }
    if(merchInterest){
      document.getElementById('enrolment-review').innerHTML=`<div><span>Enquiry type</span><strong>HV Swim Collection</strong><small>Pre-launch merchandise interest</small></div><div><span>Saved preferences</span><strong>${esc(merchInterest)}</strong><small>No stock is reserved and no payment is taken</small></div><div><span>Next step</span><strong>Team follow-up</strong><small>Final products, options and launch timing are confirmed personally</small></div>`;
      return;
    }
    const confidence=form.querySelector('[name="confidence"]:checked')?.value||'Not supplied';
    const goal=elements.goal.selectedOptions[0]?.textContent||'Not supplied';
    document.getElementById('enrolment-review').innerHTML=`<div><span>Swimmer</span><strong>${esc(elements.swimmerName.value||'Merchandise enquiry')}</strong><small>${esc(elements.age.value||'Not applicable')}</small></div><div><span>Suggested pathway</span><strong>${esc(elements.program.value||'Team recommendation')}</strong><small>${esc(confidence)} · ${esc(goal)}</small></div><div><span>Class preference</span><strong>${esc(elements.preferredClass.value||'Flexible')}</strong><small>${esc(elements.preferredDays.value||'No other days selected')}</small></div>`;
  }
  function composeExperience(){
    if(!lessonEnquiry())return elements.notes.value.trim();
    const confidence=form.querySelector('[name="confidence"]:checked')?.value||'Not supplied';
    const goal=elements.goal.selectedOptions[0]?.textContent||'Not supplied';
    return `Confidence: ${confidence}. Main goal: ${goal}.${queryLocation?` Preferred location: ${queryLocation}.`:''}${elements.notes.value.trim()?` Additional context: ${elements.notes.value.trim()}`:''}`;
  }

  elements.next.addEventListener('click',()=>{if(validateStep(currentStep)){if(currentStep===2)recommendation();showStep(currentStep+1);}});
  elements.back.addEventListener('click',()=>showStep(currentStep-1));
  elements.contactMethod.addEventListener('change',syncPhoneRequirement);
  form.addEventListener('change',event=>{if(['confidence','swimmer-goal'].includes(event.target.name)||['swimmer-goal','swimmer-age'].includes(event.target.id))recommendation();saveDraft();});
  form.addEventListener('submit',async event=>{
    event.preventDefault();
    if(lessonEnquiry()){
      for(const step of [1,2,3]){if(!validateStep(step)){showStep(step,false);validateStep(step);return;}}
    }
    if(!validateStep(4))return;
    elements.experience.value=composeExperience().slice(0,500);
    elements.preferredDays.value=[...form.querySelectorAll('[name="preferred_day"]:checked')].map(input=>input.value).join(', ');
    const payload=Object.fromEntries(new FormData(form).entries());
    payload.acknowledgement=!!form.querySelector('[name="acknowledgement"]')?.checked;
    delete payload.confidence;delete payload.class_choice;delete payload.preferred_day;
    elements.submit.disabled=true;elements.submit.textContent='Sending securely…';elements.error.textContent='';
    try{
      const result=await request('/api/public/enquiries',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)},12000);
      form.hidden=true;document.querySelector('.enrolment-progress').hidden=true;
      document.getElementById('success-reference').textContent=result.reference||`HV-ENQ-${String(result.id).padStart(4,'0')}`;
      const success=document.getElementById('enrolment-success');success.hidden=false;
      document.querySelector('[data-lesson-guidance]').hidden=true;
      clearDraft();
      success.scrollIntoView({behavior:scrollBehavior(),block:'center'});
      requestAnimationFrame(()=>success.querySelector('h2')?.focus({preventScroll:true}));
    }catch(problem){elements.error.textContent=`${problem.message} Please try again or call 0413 462 112.`;elements.submit.disabled=false;elements.submit.innerHTML='Send secure enquiry <span aria-hidden="true">→</span>';}
  });

  request('/api/classes',{headers:{Accept:'application/json'}}).then(payload=>{classes=payload.classes||[];renderClasses();}).catch(()=>{document.getElementById('wizard-class-grid').innerHTML='<label class="wizard-class-card flexible"><input type="radio" name="class_choice" value="Flexible—team recommendation"><span class="class-choice-check">✓</span><div><span class="class-match-label">Timetable unavailable</span><strong>Keep me flexible</strong><small>The team will check the current classes and recommend a suitable time when they reply.</small></div></label>';});

  document.querySelectorAll('.wizard-heading h2').forEach(heading=>heading.tabIndex=-1);
  function updateEnquiryType(){
    const isLesson=lessonEnquiry();
    document.querySelector('.enrolment-hero-trust').hidden=!isLesson;
    document.querySelector('[data-lesson-guidance]').hidden=!isLesson;
    document.body.classList.toggle('is-contact-enquiry',!isLesson);
    heroHeading.innerHTML=isLesson?lessonHeading:'Talk to <span>the HV Swim team.</span>';
    heroCopy.textContent=isLesson?lessonCopy:'Questions about your account, invoices or the collection? Send a message and the team will follow up using your preferred contact method.';
    contactCopyTargets.forEach(({element,contact,lesson})=>{if(element)element.innerHTML=isLesson?lesson:contact;});
    document.querySelector('.enrolment-progress').hidden=!isLesson;
    document.querySelector('.enrolment-topline').hidden=!isLesson;
    for(const step of [1,2,3])stepElement(step).querySelectorAll('input,select,textarea').forEach(input=>{input.disabled=!isLesson;});
    elements.notes.required=!isLesson;
    elements.notes.placeholder=isLesson?'Optional—current skills, past lessons or what success would look like':'How can the team help? Please keep detailed medical information out of this form.';
    const support=document.getElementById('support-needs');
    support.disabled=!isLesson;
    support.closest('.field').hidden=!isLesson;
    document.querySelector('label[for="experience-notes"]').textContent=isLesson?'Anything else about their experience or goals?':'Your message';
    if(!isLesson)document.getElementById('enquiry-draft-notice').hidden=true;
    showStep(isLesson?1:4,false);
  }
  enquiryType.addEventListener('change',updateEnquiryType);
  document.querySelector('#enrolment-success h2')?.setAttribute('tabindex','-1');
  syncPhoneRequirement();
  if(!merchInterest){
    const draft=readDraft();
    const confidenceValues=[...form.querySelectorAll('[name="confidence"]')].map(input=>input.value);
    const queryConfidenceMap={new:'New, cautious or nervous around water',supported:'Comfortable with support',independent:'Swimming independently'};
    const preferredConfidence=queryConfidenceMap[matcherConfidence]||'';
    const preferredGoal=['confidence','skills','safety','technique','personal'].includes(matcherGoal)?matcherGoal:'';
    if(draft&&typeof draft==='object'){
      if(draft.age)elements.age.value=draft.age;
      const savedConfidence=confidenceValues.includes(draft.confidence)?draft.confidence:'';
      const confidence=preferredConfidence||savedConfidence;
      if(confidence)form.querySelectorAll('[name="confidence"]').forEach(input=>input.checked=input.value===confidence);
      elements.goal.value=preferredGoal||draft.goal||'';
      if(!queryProgram&&draft.program)elements.program.value=draft.program;
      if(!queryClass&&draft.preferredClass)elements.preferredClass.value=draft.preferredClass;
      if(Array.isArray(draft.preferredDays))form.querySelectorAll('[name="preferred_day"]').forEach(input=>input.checked=draft.preferredDays.includes(input.value));
      elements.preferredDays.value=[...form.querySelectorAll('[name="preferred_day"]:checked')].map(input=>input.value).join(', ');
      const hasSavedChoice=Boolean(draft.age||draft.confidence||draft.goal||draft.program||draft.preferredClass||(Array.isArray(draft.preferredDays)&&draft.preferredDays.length));
      document.getElementById('enquiry-draft-notice').hidden=!hasSavedChoice;
    }else{
      if(preferredConfidence)form.querySelectorAll('[name="confidence"]').forEach(input=>input.checked=input.value===preferredConfidence);
      if(preferredGoal)elements.goal.value=preferredGoal;
    }
    const incomingAge=incoming.get('matcher_age')||'';
    if(incoming.has('matcher_age')) elements.age.value=[...elements.age.options].some(option=>option.value===incomingAge)?incomingAge:'';
    if((form.querySelector('[name="confidence"]:checked')&&elements.goal.value)||queryProgram)recommendation();
  }
  document.getElementById('enquiry-draft-clear')?.addEventListener('click',()=>{
    clearDraft();
    elements.age.value='';elements.goal.value='';elements.program.value=queryProgram||'';elements.preferredClass.value=queryLocation?`Location preference: ${queryLocation}`:'';elements.preferredDays.value='';
    form.querySelectorAll('[name="confidence"],[name="preferred_day"],[name="class_choice"]').forEach(input=>input.checked=false);
    const recommendationPanel=document.getElementById('pathway-recommendation');
    recommendationPanel.classList.remove('ready');
    recommendationPanel.innerHTML='<span>Suggested pathway</span><strong>Complete both choices to see a starting point.</strong><p>The HV Swim team will personally confirm the final class match.</p>';
    document.getElementById('enquiry-draft-notice').hidden=true;
    showStep(1,false);
    elements.age.focus();
  });
  if(queryProgram&&!form.querySelector('[name="confidence"]:checked')&&!elements.goal.value){elements.program.value=queryProgram;document.getElementById('pathway-recommendation').innerHTML=`<span>Selected pathway</span><strong>${esc(queryProgram)}</strong><p>Complete the confidence questions so the team can confirm this starting point.</p>`;}
  if(queryLocation){
    elements.preferredClass.value=`Location preference: ${queryLocation}`;
    const heroCopy=document.querySelector('.enrolment-hero-grid > div > p');
    if(heroCopy)heroCopy.textContent=`${queryLocation} is saved as your preferred location. Tell us about the swimmer so the team can confirm a suitable program, class and time.`;
    const classCopy=stepElement(3)?.querySelector('.wizard-heading p');
    if(classCopy)classCopy.textContent=`Preferred venue: ${queryLocation}. Select a current class as a preference, or stay flexible and let the team recommend one.`;
  }
  document.querySelectorAll('a[href="#enrolment"]').forEach(link=>link.addEventListener('click',event=>{
    event.preventDefault();
    history.replaceState(null,'','#enrolment');
    showStep(currentStep,true);
  }));
  if(merchInterest){
    enquiryType.value='merchandise';
    elements.swimmerName.value='Merchandise enquiry';elements.age.value='Adult';elements.program.value='HV Swim Collection';elements.preferredClass.value='Not applicable';elements.notes.value=merchInterest;
    document.querySelector('.enrolment-hero h1').innerHTML='Your collection <span>interest is ready.</span>';
    document.querySelector('.enrolment-hero-grid > div > p').textContent='Add your contact details and send the saved merchandise preferences directly to the HV Swim team before the collection launches.';
    updateEnquiryType();
  }else{
    if(termWeeks){
      const weeks=Number(termWeeks);
      if(Number.isInteger(weeks)&&weeks>=8&&weeks<=12){
        const privateLesson=lessonFormat==='Private 1:1 Tuition';
        elements.notes.value=`Term enquiry: ${weeks} weeks (${privateLesson?'Private 1:1 Tuition':'Standard Lesson'}). ${privateLesson?'Pricing to be confirmed by the team.':`Indicative estimate $${(weeks*22.50).toFixed(2)}; lesson count to be confirmed.`}`;
      }
    }
    showStep(1,false);
    if(queryProgram&&!form.querySelector('[name="confidence"]:checked')&&!elements.goal.value)elements.program.value=queryProgram;
  }
})();
