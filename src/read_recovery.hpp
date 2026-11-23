#pragma once
#include <cstdint>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
// Host-side policy for injected OCP Table 12 responses, NOT an ECC decoder.
// Topology is explicit test geometry: 2 dies, 2 banks/die, 2 blocks/bank.
class ReadRecovery {
 struct Request {unsigned block,stage=0,attempts=0;};
 struct Refresh {unsigned next=0,pages;};
 std::map<unsigned,Request> requests;
 std::map<unsigned,Refresh> refreshes;
 std::set<unsigned> blocked,retired,dirty;
 static unsigned die(unsigned b){return b/4;}
 void valid(unsigned b)const{if(b>=8)throw std::invalid_argument("block out of range");}
public:
 bool issue(unsigned id,unsigned b){valid(b);
  if(requests.count(id))throw std::invalid_argument("duplicate logical read");
  if(blocked.count(die(b))||retired.count(b)||dirty.count(b)||refreshes.count(b))return false;
  requests.emplace(id,Request{b});return true;
 }
 std::string response(unsigned id,unsigned status,unsigned info,bool payload_valid){
  auto i=requests.find(id);if(i==requests.end())throw std::invalid_argument("unknown response");
  if(info>7||!((status==0&&info==0)||(status==4&&(info==1||info==2))||
    (status==5&&(info==1||info==2))||status==6||(status==8&&info>=1&&info<=4)||(status==9&&info==1)))
   throw std::invalid_argument("unsupported status or reserved metadata");
  if(payload_valid!=(status==0||status==5))throw std::invalid_argument("invalid payload validity");
  auto&r=i->second;unsigned b=r.block;
  if(status==6){if(++r.attempts>3){requests.erase(i);return "retry_exhausted";}r.stage=info;return "retry:"+std::to_string(info);}
  if(status==4||status==5)dirty.insert(b);
  if(status==9)blocked.insert(die(b));
  if(status==8)for(unsigned n=0;n<8;++n)
   if(info==4||(info==3&&die(n)==die(b))||(info==2&&n/2==b/2)||(info==1&&n==b))retired.insert(n);
  requests.erase(i);
  return status==0?"deliver":status==5?"deliver_refresh":status==4?"backup_required":status==8?"retired":"poll_die";
 }
 unsigned retry_stage(unsigned id)const{return requests.at(id).stage;}
 void poll(unsigned d,bool ready){if(d>=2)throw std::invalid_argument("invalid die");if(ready)blocked.erase(d);}
 bool writable(unsigned b)const{valid(b);return !blocked.count(die(b))&&!retired.count(b)&&!refreshes.count(b)&&!dirty.count(b);}
 void begin_refresh(unsigned b,unsigned pages,bool complete_backup){valid(b);
  if(!complete_backup||!pages||!dirty.count(b)||retired.count(b)||blocked.count(die(b))||refreshes.count(b))throw std::invalid_argument("unsafe refresh");
  for(auto&[id,r]:requests)if(r.block==b)throw std::invalid_argument("refresh with outstanding reader");
  refreshes.emplace(b,Refresh{0,pages});
 }
 // Acknowledgements must come from the real write path; no timer clears health.
 void page_written(unsigned b,unsigned page,bool success){auto i=refreshes.find(b);
  if(i==refreshes.end()||page!=i->second.next)throw std::invalid_argument("refresh order");
  if(blocked.count(die(b))||retired.count(b))throw std::invalid_argument("refresh on unavailable die");
  if(!success){refreshes.erase(i);return;}
  if(++i->second.next==i->second.pages){refreshes.erase(i);dirty.erase(b);}
 }
};
