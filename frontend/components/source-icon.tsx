import { Mail, FileText, Diamond } from 'lucide-react';
export function SourceIcon({ type }: { type: string }) { return <span className={`source-icon ${type}`} aria-hidden="true">{type==='gmail'?<Mail/>:type==='jira'?<Diamond/>:type==='notion'?<b>N</b>:<FileText/>}</span>; }
