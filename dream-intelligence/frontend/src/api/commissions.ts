export interface CommissionLead {
  id:number;title:string;url:string;source:string;source_name:string;description:string;
  budget:string|null;deadline:string|null;publisher:string|null;published_on:string|null;
  confirmed_on:string|null;source_status:string;status:string;category:string;
  source_status_text?:string;deadline_at?:string|null;deadline_kind?:string;delivery_deadline?:string|null;
  region:string;region_evidence:string|null;checked_at:string;captured_at:string;
}
export interface CommissionSource {
  source:string;name:string;url:string;status:string;checked:number;accepted:number;errors:string[];coverage?:string;
}
export interface CommissionView {
  leads:CommissionLead[];sources:{id:string;name:string;url:string;coverage?:string}[];
  latest:null|{id:number;status:string;started_at:string;finished_at:string|null;
    inserted?:number;updated?:number;received?:number;sources?:CommissionSource[]};
}
const base='http://127.0.0.1:8000/api/v1/commissions';
async function checked(response:Response):Promise<CommissionView> {
  if(!response.ok)throw new Error(response.status===409?'另一项采集正在运行，请稍后重试。':'商单资料暂时无法读取，请检查本地服务。');
  return response.json();
}
export async function getCommissions(signal?:AbortSignal) {return checked(await fetch(base,{signal}));}
export async function collectCommissions() {return checked(await fetch(`${base}/collect`,{method:'POST'}));}
