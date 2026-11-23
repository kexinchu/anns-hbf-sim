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
 unsigned stripe=argc>1?std::stoul(argv[1]):64,target=argc>2?std::stoul(argv[2]):0;int seed=argc>3?std::stoi(argv[3]):10;
 std::string mutation=argc>4?argv[4]:"";
 SimulationConfiguration cfg;cfg.device.geometry.host_channels=2;cfg.address.interleave_bytes=stripe;cfg.host.max_resident_fragments=1024;
 SimulationSession session(resolve_configuration(cfg));VersionedPages pages(4);EventLabPageGroup group(pages);
 bool armed=false,injected=false,old_active=false;int oldframe=-1;unsigned reads=0,parents=0;std::optional<EventLabPageGroup::Ack> ack;
 race_init();
 auto snapshot=[&](const char* event){auto st=session.host().statistics();std::cout<<"{\"event\":\""<<event<<"\",\"frames\":[";for(int i=0;i<4;i++){auto&f=pages.frames[i];std::cout<<(i?",":"")<<"["<<f.page<<","<<f.generation<<",\""<<f.state<<"\","<<f.pins<<","<<f.dirty<<"]";}std::cout<<"],\"accepted\":"<<st.accepted<<",\"responses\":"<<st.responses<<",\"errors\":"<<st.attempt_errors<<",\"replay\":"<<st.replay_commands<<",\"old_pending\":"<<(old_active&&!race_ready(oldframe)?"true":"false")<<"}\n";};
 session.set_program_outcome([&](const ProgramOperation& op){if(armed&&!injected&&op.logical.channel==target){injected=true;need(old_active&&!race_ready(oldframe),"no live CUDA race during failure");snapshot("program_fail");return ProgramOutcome::FailedReusable;}return ProgramOutcome::Success;});
 session.set_completion_handler([&](const GlobalCompletion& c){
  if(c.result.id.value>=1000){++parents;auto a=group.completion(c);if(a)ack=*a;
   else{need(!ack,"early aggregate");snapshot("partial_parent");}
  }else{need(c.result.state==LogicalResult::Success,"wire read/setup failure");if(c.result.id.value>=500)++reads;}
 });
 auto drain=[&]{auto r=session.advance_until_yield();need(r.run.status==RunStatus::WaitingForInput&&r.run.workload_success,"backend drain");};
 std::vector<GlobalRequest> init;for(int p=0;p<4;p++)init.push_back({GlobalRequestId{std::uint64_t(p+1)},Op::Write,GlobalByteAddress{std::uint64_t(p)*4096},4096,1});session.submit(init);drain();
 auto read=[&](int p,unsigned id,unsigned content){GlobalRequest r{GlobalRequestId{id},Op::Read,GlobalByteAddress{std::uint64_t(p)*4096},4096};r.expected_content=content;r.not_before=Tick{session.now().value+1};session.submit(r);drain();};
 auto fill=[&](int ticket,int p,int value){need(pages.begin(ticket,p)=="accepted","fill admission");int f=pages.fills.at(ticket).frame;race_fill(f,value);need(pages.publish(ticket,true)=="ready","H2D publication");return f;};
 read(2,500,1);oldframe=fill(1,2,seed+20);need(pages.acquire(1,2)=="acquired","old reader");race_start(oldframe,true);old_active=true;
 need(pages.refresh(2)=="refreshed","refresh race");snapshot("old_retired");
 auto loadgroup=[&](int first,int value,int ticket){for(int i=0;i<2;i++){int f=fill(ticket+i,first+i,value+10*i);std::array<int,1024> copy;race_copy(f,copy.data());for(int j=0;j<1024;j++)need(copy[j]==value+10*i+j%17,"D2H payload mismatch");need(pages.dirty(first+i)=="dirty","dirty");}};
 loadgroup(0,seed+100,10);
 reject([&]{group.submit(session,1000,0,2,{true});});
 reject([&]{group.submit(session,1000,0,2,{true,false});});snapshot("before_group");
 armed=true;group.submit(session,1000,0,2,{true,true});snapshot("submitted");drain();need(injected&&ack.has_value(),"missing recovered aggregate");
 snapshot("recovered_held");need(pages.release(1,race_ready(oldframe))=="pending","early CUDA release");
 auto oldack=*ack;auto partial=oldack;partial.pop_back();need(group.deliver(partial)=="stale_ack","partial ACK escaped");
 need(group.deliver(oldack)=="committed","first group commit");snapshot("first_commit");
 for(int p=0;p<2;p++)need(pages.dirty(p)=="dirty","second dirty");ack.reset();group.submit(session,1100,0,3,{true,true});
 auto stale=oldack;if(mutation=="misbind_ack")for(auto&a:stale){auto w=pages.writebacks.at(a.page);pages.written(a.page,w.token,w.epoch,true,true);}
 need(group.deliver(stale)=="stale_ack","old aggregate escaped");snapshot("old_ack_rejected");drain();need(ack&&group.deliver(*ack)=="committed","second aggregate");for(int p=0;p<2;p++)need(pages.evict(p)=="evicted","group eviction");
 loadgroup(2,seed+200,20);ack.reset();group.submit(session,1200,2,3,{true,true});drain();need(ack&&group.deliver(*ack)=="committed","prefix restoration");
 read(2,501,3);int fresh=pages.resident(2);need(pages.acquire(2,2)=="acquired","fresh lease");race_start(fresh,false);long long current[32],old[32];race_result(fresh,current);need(pages.release(2,race_ready(fresh))=="released","fresh release");snapshot("fresh_done_old_pending");
 if(mutation=="reuse_old_frame") {race_open(oldframe);race_result(oldframe,old);race_fill(oldframe,seed+999);race_start(oldframe,false);}
 race_open(oldframe);race_result(oldframe,old);need(pages.release(1,race_ready(oldframe))=="released","old release");old_active=false;snapshot("old_released");
 for(auto item:{std::make_pair("old",old),std::make_pair("new",current)}){std::cout<<"{\"answer\":\""<<item.first<<"\",\"scores\":[";for(int i=0;i<32;i++)std::cout<<(i?",":"")<<item.second[i];std::cout<<"],\"top10\":[";std::array<int,32> rank;for(int i=0;i<32;i++)rank[i]=i;std::sort(rank.begin(),rank.end(),[&](int a,int b){return std::make_pair(item.second[a],a)<std::make_pair(item.second[b],b);});for(int i=0;i<10;i++)std::cout<<(i?",":"")<<64+rank[i];std::cout<<"]}\n";}
 auto st=session.host().statistics();need(reads==2&&parents==6,"completion accounting");
 std::cout<<"{\"status\":\"PASS\",\"backend\":\""
#ifdef ANNS_CUDA
 <<"CUDA_A6000"
#else
 <<"CPU"
#endif
 <<"\",\"accepted\":"<<st.accepted<<",\"responses\":"<<st.responses<<",\"errors\":"<<st.attempt_errors<<",\"replay\":"<<st.replay_commands<<",\"performance_ready\":false}\n";
 race_close();
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';race_close();return 1;}}
