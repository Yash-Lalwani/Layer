export const sources = [
 { id:1, type:'drive', name:'Google Drive', title:'Phoenix PRD v3', detail:'Project goals', text:'Goal: ship self-serve onboarding by the end of Q4.' },
 { id:2, type:'notion', name:'Notion', title:'Q4 Plan: Phoenix', detail:'This quarter’s tasks', text:'12 tasks across design, backend, and QA. Design reviews finish first.' },
 { id:3, type:'jira', name:'Jira', title:'Payments API', detail:'Open blockers', text:'Two tickets are blocked on the payments API. Waiting on the payments team.' },
 { id:4, type:'gmail', name:'Gmail', title:'Re: Phoenix launch date', detail:'Latest decisions', text:'We’re moving launch to Nov 15 to give QA another week.' },
];
export const questions: Record<string,{label:string;title:string;lines:{text:string;source:number}[]}> = {
 overview:{label:'What’s the big picture?',title:'Here’s the big picture.',lines:[{text:'Phoenix is building self-serve onboarding for Q4.',source:1},{text:'12 tasks are planned, starting with design reviews.',source:2},{text:'Two tickets are waiting on the payments API.',source:3},{text:'The launch date has moved to November 15.',source:4}]},
 blockers:{label:'What’s blocking launch?',title:'Two blockers. One dependency.',lines:[{text:'Two tickets are blocked by the payments API.',source:3},{text:'The work is waiting on the payments team.',source:3},{text:'The launch is now November 15, giving QA an extra week.',source:4}]},
 changes:{label:'What changed this week?',title:'A new date. More room for QA.',lines:[{text:'The launch date has moved to November 15.',source:4},{text:'The change gives QA another week.',source:4},{text:'The Q4 plan lists 12 tasks across design, backend, and QA.',source:2}]}
};
export async function getDemoAnswer(key:string) { await new Promise(resolve=>setTimeout(resolve,300)); return questions[key] ?? questions.overview; }
