/* Shared guidance only. Teaching staff confirm every placement. */
(() => {
  'use strict';
  window.HVLessonPathway = ({age = '', confidence = '', goal = ''} = {}) => {
    const infant = ['under2', 'Approximately 4–12 months', '1–2 years'].includes(age);
    const older = ['teenadult', 'Teen', 'Adult'].includes(age);
    const independent = ['independent', 'Swimming independently'].includes(confidence);
    const personal = goal === 'personal' || confidence.includes('one-to-one');
    if (personal) return {title:'Private 1:1 Lesson', anchor:'private', explanation:'Tell us about the swimmer’s age and goals. The team can discuss whether one-to-one support is suitable and confirm an appropriate starting point.'};
    if (infant) return {title:'Infant Aquatics', anchor:'infant', explanation:'A carer-supported infant program introduces comfortable early water experiences. Age and readiness are confirmed with the teaching team.'};
    if (older && !independent) return {title:'Adult / Teen Private Assessment', anchor:'private', explanation:'A calm private assessment gives a teen or adult a personal starting point. We begin with comfort and core skills before progressing to technique.'};
    if (independent) return {title:'Stroke Development', anchor:'stroke', explanation:'Because the swimmer is already swimming independently, a technique-focused pathway may help develop breathing, movement and endurance. The team confirms readiness first.'};
    return {title:'Learn to Swim', anchor:'learn', explanation:goal === 'technique' ? 'Technique is a useful goal. We start by building confidence and independent core skills, then the teaching team can guide progression towards stroke development.' : 'A small-group learn-to-swim pathway can build confidence and core skills at the swimmer’s pace. The exact level is confirmed personally.'};
  };
})();
