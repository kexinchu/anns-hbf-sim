#include "eventlab_page_group.hpp"
#include <algorithm>
#include <array>
#include <iostream>
#ifdef ANNS_CUDA
#include "../gpu/race_backend.h"
#else
namespace {int values[4];bool held[4]{};}
void race_init(){} void race_fill(int f,int v){values[f]=v;}void race_start(int f,bool h){held[f]=h;}
bool race_ready(int f){return !held[f];}void race_open(int f){held[f]=false;}
void race_result(int f,long long* a){for(int k=0;k<32;k++){a[k]=0;for(int j=0;j<32;j++){long long d=values[f]+(k*32+j)%17-3;a[k]+=d*d;}}}
void race_copy(int f,int* a){for(int i=0;i<1024;i++)a[i]=values[f]+i%17;}void race_close(){}
#endif
using namespace hbf_eventlab;
void need(bool b,const char* msg){if(!b)throw std::runtime_error(msg);}
template<class F> void reject(F f){bool yes=false;try{f();}catch(const std::invalid_argument&){yes=true;}need(yes,"negative escaped");}

int main(int argc,char**argv){try{
 unsigned mode=argc>1?std::stoul(argv[1]):0,target=argc>2?std::stoul(argv[2]):0;
 std::string mutation=argc>3?argv[3]:"";need(mode<9&&target<2,"invalid profile");
 SimulationConfiguration cfg;cfg.device.geometry.host_channels=2;cfg.host.max_resident_fragments=1024;
 SimulationSession session(resolve_configuration(cfg));VersionedPages pages(4);EventLabPageGroup group(pages);
 reject([&]{group.reset_begin(2);});need(!group.cancel(999),"unknown cancel");
 race_init();int old=-1;unsigned faults=0,done=0;bool armed=false;std::optional<EventLabPageGroup::Ack> ack;
 auto snap=[&](const char* event){std::cout<<"{\"event\":\""<<event<<"\",\"frames\":[";
  for(int i=0;i<4;i++){auto&f=pages.frames[i];std::cout<<(i?",":"")<<"["<<f.page<<","<<f.generation<<",\""<<f.state<<"\","<<f.pins<<","<<f.dirty<<"]";}
  auto s=session.host().statistics();std::cout<<"],\"accepted\":"<<s.accepted<<",\"responses\":"<<s.responses<<",\"errors\":"<<s.attempt_errors<<",\"replay\":"<<s.replay_commands<<",\"faults\":"<<faults<<",\"parents\":"<<done<<",\"old_pending\":"<<(!race_ready(old)?"true":"false")<<"}\n";};
 auto fence=[&]{if(mode==2||mode==3||mode==7)group.reset_begin(0);else need(group.cancel(1000),"cancel missing");snap("fenced");};
 session.set_program_outcome([&](const ProgramOperation&o){
  if(armed&&(mode==4||mode==5||mode==8)&&(mode==5||o.logical.channel==target)&&(mode!=4||faults==0)){
   need(!race_ready(old),"fault outside race");++faults;return ProgramOutcome::FailedUnusable;}
  return ProgramOutcome::Success;
 });
 session.set_completion_handler([&](const GlobalCompletion&c){++done;auto a=group.completion(c);if(a)ack=*a;
  if(done==1&&(mode==6||mode==7))fence();snap("parent");});
 auto fill=[&](int p,int value){need(pages.begin(p,p)=="accepted","fill");int f=pages.fills.at(p).frame;race_fill(f,value);need(pages.publish(p,true)=="ready","publish");return f;};
 old=fill(2,30);need(pages.acquire(1,2)=="acquired","old lease");race_start(old,true);
 int healthy=fill(4,40);for(int p=0;p<2;p++){int f=fill(p,100+p*10);int bytes[1024];race_copy(f,bytes);for(int i=0;i<1024;i++)need(bytes[i]==100+p*10+i%17,"backup mismatch");need(pages.dirty(p)=="dirty","dirty");}
 armed=true;group.submit(session,1000,0,1,{true,true});snap("submitted");
 if(mode==0||mode==2)fence();
 if(mode==2)need(group.reset_finish(session,0,true)=="draining","early reset completion");
 if(mode==2){need(pages.acquire(9,2)=="blocked","reset admission");
  reject([&]{group.reset_begin(0);});reject([&]{group.submit(session,9000,0,9,{true,true});});}
 auto r=session.advance_until_yield();need(r.run.status==RunStatus::WaitingForInput,"drain stopped");need(done==2&&ack.has_value(),"missing terminal");
 auto late=*ack;
 if(mode==1||mode==3)fence();
 if(mode!=4&&mode!=5&&mode!=8){
  auto forged=late;for(auto&a:forged)a.success=true;
  if(mutation=="stale_commit")for(auto&a:forged)pages.written(a.page,a.token,a.epoch,true,true);
  need(group.deliver(forged)=="stale_ack","revoked ACK accepted");
 }
 if(mode==2||mode==3||mode==7)need(group.reset_finish(session,0,true)=="draining","unacknowledged reset");
 auto terminal=group.terminal_ack(1000);auto result=group.deliver(terminal);
 need(result==(mode==4?"committed":"failed"),"terminal policy");
 need(group.deliver(late)=="stale_ack","duplicate late ACK");need(!group.cancel(1000),"cancel completed owner");snap("settled");
 if(mode==2||mode==3||mode==7){
  need(group.reset_finish(session,0,false)=="not_ready","reset readiness");
  need(group.reset_finish(session,0,true)=="resumed","reset finish");
  need(group.reset_finish(session,0,true)=="invalid","duplicate reset");
 }else need(pages.refresh(2)=="refreshed","old retire");
 need(pages.release(1,race_ready(old))=="pending","early reclaim");
 need(pages.acquire(2,4)=="acquired","other scope isolation");race_start(healthy,false);long long scores[32];race_result(healthy,scores);need(pages.release(2,race_ready(healthy))=="released","healthy release");snap("isolated");
 if(mode!=4){for(int p=0;p<2;p++)need(pages.evict(p)=="busy","dirty data lost");}
 if(mode!=5&&mode!=8){ // Explicit ordered page-zero replay, same session, fresh identity.
  if(mode==4)for(int p=0;p<2;p++)need(pages.dirty(p)=="dirty","replay dirty");
  ack.reset();group.submit(session,2000,0,2,{true,true});
  need(group.deliver(late)=="stale_ack","old ACK crossed retry");
  auto retry=session.advance_until_yield();need(retry.run.status==RunStatus::WaitingForInput&&ack.has_value(),"retry drain");
  need(group.deliver(*ack)=="committed","replay commit");
 }else need(!r.run.workload_success,"exhaustion reported success");
 snap(mode==5||mode==8?"exhausted":"replayed");
 if(mutation=="reuse_frame"){race_open(old);race_result(old,scores);race_fill(old,999);race_start(old,false);}
 race_open(old);race_result(old,scores);need(pages.release(1,race_ready(old))=="released","old release");
 std::cout<<"{\"scores\":[";for(int i=0;i<32;i++)std::cout<<(i?",":"")<<scores[i];std::cout<<"],\"backend\":\""
#ifdef ANNS_CUDA
 <<"CUDA_A6000"
#else
 <<"CPU"
#endif
 <<"\",\"performance_ready\":false}\n";race_close();
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';race_close();return 1;}}
