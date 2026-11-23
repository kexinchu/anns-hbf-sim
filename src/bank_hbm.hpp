#pragma once
#include <algorithm>
#include <cstdint>
#include <deque>
#include <optional>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>
// Explicit-cycle, one-PC, bank-parallel research controller. Parameters are cycles,
// not a JEDEC part specification. No donor look-ahead or service_request calls.
class BankHbm {
public:
 using U=std::uint64_t;
 struct Timing {U rcd=4,rp=4,ras=8,rc=12,cl=4,cwl=3,burst=2,ccd=2,rrd=2,faw=8,rtp=2,wr=3,turn=2;};
 struct Event {U tick,id,bank,row;std::string op;};
private:
 struct Request {U id,bank,row,arrival;bool write;};
 struct Bank {std::optional<U> row;U column=0,pre=0,activate=0;std::deque<Request> q;};
 struct Done {U at;Request r;};
 Timing t;std::vector<Bank> banks;std::vector<Done> pending;std::deque<U> acts;
 U capacity,used=0,clock=0,command_free=0,column_free=0,act_free=0,bus_free=0;bool stepped=false;
 std::optional<bool> last_write;
public:
 BankHbm(U count,U limit):banks(count),capacity(limit){if(!count||!limit)throw std::invalid_argument("zero geometry");}
 bool submit(U now,U id,U bank,U row,bool write){
  if(bank>=banks.size()||now!=(stepped?clock+1:0))throw std::invalid_argument("invalid bank or nonfuture arrival");
  if(used==capacity)return false;
  for(auto&b:banks)for(auto&r:b.q)if(r.id==id)throw std::invalid_argument("duplicate id");
  for(auto&d:pending)if(d.r.id==id)throw std::invalid_argument("duplicate id");
  banks[bank].q.push_back({id,bank,row,now,write});++used;return true;
 }
 std::vector<Event> step(U now){
  if(stepped&&now!=clock+1)throw std::invalid_argument("must step every cycle");
  if(!stepped&&now!=0)throw std::invalid_argument("start at zero");
  stepped=true;clock=now;std::vector<Event> result;
  for(auto i=pending.begin();i!=pending.end();)if(i->at==now){auto r=i->r;result.push_back({now,r.id,r.bank,r.row,"DONE"});--used;i=pending.erase(i);}else ++i;
  while(!acts.empty()&&acts.front()+t.faw<=now)acts.pop_front();
  struct Candidate {U bank,arrival,id;int kind;};std::vector<Candidate> candidates;
  if(now>=command_free)for(U k=0;k<banks.size();++k){auto&b=banks[k];if(b.q.empty()||b.q.front().arrival>now)continue;auto&r=b.q.front();int kind=-1;
   if(!b.row){if(now>=b.activate&&now>=act_free&&acts.size()<4)kind=1;}
   else if(*b.row!=r.row){if(now>=b.pre)kind=2;}
   else {U latency=r.write?t.cwl:t.cl;
    U gap=last_write&&*last_write!=r.write?t.turn:0;
    if(now>=b.column&&now>=column_free&&now+latency>=bus_free+gap)kind=0;
   }
   if(kind>=0)candidates.push_back({k,r.arrival,r.id,kind});
  }
  // Ready column first; after 32 cycles the oldest ready request wins.
  std::sort(candidates.begin(),candidates.end(),[&](auto&a,auto&b){
   bool aa=now-a.arrival>=32,bb=now-b.arrival>=32;
   if(aa!=bb)return aa;if(!aa&&a.kind!=b.kind)return a.kind<b.kind;
   return std::tie(a.arrival,a.id,a.bank)<std::tie(b.arrival,b.id,b.bank);
  });
  if(candidates.empty())return result;
  auto c=candidates.front();auto&b=banks[c.bank];auto r=b.q.front();command_free=now+1;
  if(c.kind==1){b.row=r.row;b.column=now+t.rcd;b.pre=now+t.ras;b.activate=now+t.rc;act_free=now+t.rrd;acts.push_back(now);result.push_back({now,r.id,r.bank,r.row,"ACT"});}
  else if(c.kind==2){b.row.reset();b.activate=std::max(b.activate,now+t.rp);result.push_back({now,r.id,r.bank,r.row,"PRE"});}
  else {U end=now+(r.write?t.cwl:t.cl)+t.burst;bus_free=end;column_free=now+t.ccd;last_write=r.write;
   b.pre=std::max(b.pre,r.write?end+t.wr:now+t.rtp);pending.push_back({end,r});b.q.pop_front();result.push_back({now,r.id,r.bank,r.row,r.write?"WR":"RD"});}
  return result;
 }
 U resident()const{return used;}
};
