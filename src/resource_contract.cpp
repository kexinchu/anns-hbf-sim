#include "online_hbm.hpp"
#include "hbf_eventlab/runtime/simulation_session.hpp"
#include <iostream>
#include <sstream>
#include <queue>
#include <tuple>
using U=std::uint64_t;
void require(bool b,const char*m){if(!b)throw std::runtime_error(m);}
struct Task{U at,seq;std::function<void()> f;};
struct Later{bool operator()(const Task&a,const Task&b)const{return std::tie(a.at,a.seq)>std::tie(b.at,b.seq);}};
void hbm_test(){
 using namespace hbfsim::physical::hbm;
 HbmConfig config;config.replicate_symmetric_pseudo_channels=false;
 HbmDevice mapping(config);HbmAddress other{};other.pseudo_channel=1;U other_addr=mapping.encode(other);
 U now=0,seq=0;std::priority_queue<Task,std::vector<Task>,Later> tasks;
 std::map<U,std::vector<std::pair<U,U>>> spans;std::vector<U> completions;
 OnlineHbm hbm(config,2,[&](U t,std::function<void()> f){require(t>=now,"scheduled in past");tasks.push({t,seq++,std::move(f)});},
   [&](U lane,U a,U b,U){spans[lane].push_back({a,b});});
 auto complete=[&](U,U end){require(end==now,"callback before visibility");completions.push_back(end);};
 require(hbm.submit(0,false,0,32,complete),"first admission");
 require(hbm.submit(0,false,other_addr,32,complete),"second admission");
 require(spans.size()==2 && completions.empty(),"independent PC start / no eager callback");
 require(!hbm.submit(0,false,64,32,complete)&&hbm.resident_bursts()==2,"atomic capacity backpressure");
 while(!tasks.empty()){auto t=tasks.top();tasks.pop();now=t.at;t.f();}
 require(completions.size()==2&&completions[0]==completions[1],"independent cold PCs must overlap");
 bool past_rejected=false;try{hbm.submit(now-1,false,0,32,complete);}catch(const std::invalid_argument&){past_rejected=true;}
 require(past_rejected,"completion establishes admission time floor");
 U cold=completions[0];require(cold==30000,"independent cold analytical 30ns");
 require(hbm.submit(now,false,0,64,complete),"multi-burst request");
 while(!tasks.empty()){auto t=tasks.top();tasks.pop();now=t.at;t.f();}
 require(completions.size()==3&&hbm.resident_bursts()==0,"exactly one parent completion / drain");
 for(auto&[lane,v]:spans)for(unsigned i=1;i<v.size();i++)require(v[i].first>=v[i-1].second,"same PC overlaps");
 bool bad=false;try{hbm.submit(0,false,0,32,complete);}catch(const std::invalid_argument&){bad=true;}
 require(bad,"past arrival rejected");
 std::cout<<"{\"test\":\"online_hbm\",\"cold_ps\":"<<cold<<",\"parents\":3,\"status\":\"PASS\"}\n";
}
std::pair<U,U> core_test(U rate){
 namespace el=hbf_eventlab;el::SimulationConfiguration c;c.device.geometry.host_channels=1;
 c.execution.core_bytes_per_ns=rate;c.execution.core_propagation=el::Tick{rate?1000u:0u};
 c.execution.read_dispatch.wait=el::Tick{0};c.host.max_resident_fragments=512;
 std::ostringstream config_out;el::write_effective_configuration(config_out,el::resolve_configuration(c));
 std::istringstream config_in(config_out.str());auto parsed=el::resolve_configuration(el::read_configuration(config_in));
 require(parsed.values().execution.core_bytes_per_ns==c.execution.core_bytes_per_ns,"finite Core config roundtrip");
 el::SimulationSession session(el::resolve_configuration(c));
 auto advance=[&]{auto r=session.advance_until_yield();require(r.run.workload_success&&r.run.status==el::RunStatus::WaitingForInput,"session drain");};
 session.submit(el::GlobalRequest{el::GlobalRequestId{1},el::Op::Write,el::GlobalByteAddress{0},8192,1});advance();
 U id=2,first_latency=0;
 // Two distinct pages then page 0: both must remain in the two-buffer cache.
 for(U address:{0u,4096u,0u}){
  U arrival=session.now().value+1;session.submit(el::GlobalRequest{el::GlobalRequestId{id++},el::Op::Read,el::GlobalByteAddress{address},64,{}, {}, {},el::Tick{arrival}});advance();
  if(id==3)first_latency=session.now().value-arrival;
 }
 require(session.device().statistics().senses==2,"two cold pages require exactly two senses");
 require(session.device().statistics().cache_hits==1,"two-buffer retained page cache hit");
 return {first_latency,session.device().statistics().senses};
}
U shared_core(unsigned routes){
 namespace el=hbf_eventlab;
 struct Transfer{U ch,route,ready,start,end;};std::vector<Transfer> transfers;
 el::SimulationConfiguration c;c.device.geometry.host_channels=1;c.device.geometry.dies_per_channel=2;
 c.device.topology.core_channels_per_ucie=routes;c.execution.core_bytes_per_ns=4;
 c.execution.read_dispatch.wait=el::Tick{0};c.host.max_resident_fragments=512;
 c.execution.core_observer=[&](el::ChannelId ch,unsigned route,el::Tick ready,el::Tick start,el::Tick end){transfers.push_back({ch,route,ready.value,start.value,end.value});};
 std::ostringstream config_out;el::write_effective_configuration(config_out,el::resolve_configuration(c));
 std::istringstream config_in(config_out.str());auto parsed=el::resolve_configuration(el::read_configuration(config_in));
 require(parsed.values().execution.core_bytes_per_ns==c.execution.core_bytes_per_ns,"finite Core config roundtrip");
 el::SimulationSession session(el::resolve_configuration(c));
 auto advance=[&]{auto r=session.advance_until_yield();require(r.run.workload_success&&r.run.status==el::RunStatus::WaitingForInput,"shared session failed");};
 session.submit(el::GlobalRequest{el::GlobalRequestId{1},el::Op::Write,el::GlobalByteAddress{0},8192,1});advance();
 transfers.clear();U arrival=session.now().value+1;
 for(U i=0;i<2;i++){
  el::GlobalRequest req{el::GlobalRequestId{i+2},el::Op::Read,el::GlobalByteAddress{i*4096},64};req.not_before=el::Tick{arrival};session.submit(req);
 }
 advance();require(transfers.size()==2,"one transfer per cold page");
 for(auto t:transfers)require(t.start>=t.ready&&t.end-t.start==1024000,"finite service analytical");
 if(routes==1)require(transfers[1].start>=transfers[0].end && transfers[1].start>transfers[1].ready,"shared link must queue");
 else require(transfers[1].start<transfers[0].end,"separate links should overlap");
 return session.now().value-arrival;
}
void sense_order(){
 namespace el=hbf_eventlab;
 struct Sink:el::IStatisticsSink {
  struct Span{U ticket,page,start,end;};std::vector<Span> reads;
  void observe(const el::StatisticsEvent&e)override{
   if(auto*p=std::get_if<el::StatBankOperationStarted>(&e);p&&p->kind==el::MediaOperationKind::Read)
    reads.push_back({p->ticket,p->target.page,p->at.value,0});
   if(auto*p=std::get_if<el::StatBankOperationFinished>(&e))for(auto&s:reads)if(s.ticket==p->ticket)s.end=p->at.value;
  }
 }sink;
 el::SimulationConfiguration c;c.device.geometry.host_channels=1;c.host.max_resident_fragments=512;
 c.execution.read_dispatch.wait=el::Tick{0};c.execution.core_bytes_per_ns=32;
 el::SimulationSession session(el::resolve_configuration(c),&sink);
 auto advance=[&]{auto r=session.advance_until_yield();require(r.run.workload_success&&r.run.status==el::RunStatus::WaitingForInput,"sense session failed");};
 session.submit(el::GlobalRequest{el::GlobalRequestId{1},el::Op::Write,el::GlobalByteAddress{0},12288,1});advance();
 U arrival=session.now().value+1;
 for(U page=0;page<3;page++){
  el::GlobalRequest r{el::GlobalRequestId{page+2},el::Op::Read,el::GlobalByteAddress{page*4096},64};r.not_before=el::Tick{arrival};session.submit(r);
 }
 advance();require(sink.reads.size()==3,"all cold pages sensed");
 for(U i=0;i<3;i++){
  auto s=sink.reads[i];require(s.page==i&&s.end>s.start,"same bank sense issue order");
  if(i)require(s.start>=sink.reads[i-1].end,"same bank sense overlap");
 }
 std::cout<<"{\"test\":\"same_bank_order\",\"status\":\"PASS\"}\n";
}
int main(){try{hbm_test();sense_order();auto shared=shared_core(1),separate=shared_core(2);
 require(shared>separate,"shared Core Channel contention absent");
 std::cout<<"{\"test\":\"core_contention\",\"shared_ps\":"<<shared<<",\"separate_ps\":"<<separate<<",\"status\":\"PASS\"}\n";
auto ideal=core_test(0),finite=core_test(32);
 require(finite.first-ideal.first==129000,"cold miss adds ceil(4096*1000/32)+1000 ps");
 std::cout<<"{\"test\":\"finite_core_and_cache\",\"extra_ps\":"<<finite.first-ideal.first<<",\"status\":\"PASS\"}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
