// CPU functional fixture. GPU durations and device configuration are uncalibrated.
// EventLab is the online HBF clock. HBXim HBM is deliberately FCFS-serialized
// at the adapter boundary; this is NOT a concurrent GPU/HBM performance model.
#include "hbf_eventlab/runtime/simulation_session.hpp"
#include "physical/hbm/hbm_device.hpp"
#include "online_hbm.hpp"
#include "bank_adapter.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <cstdlib>
#include <fstream>
#include <deque>
#include <functional>
#include <iostream>
#include <map>
#include <queue>
#include <stdexcept>
#include <vector>
namespace el=hbf_eventlab;
namespace ph=hbfsim::physical;
using U=std::uint64_t;
constexpr int N=256,D=32,K=10,PS=4096,PER=PS/(D*4);
using Vec=std::array<std::int32_t,D>;
using Score=std::pair<std::int64_t,int>;
void check(bool b,const char* s){if(!b)throw std::runtime_error(s);}
std::int64_t distance(const Vec&a,const Vec&b){std::int64_t x=0;for(int j=0;j<D;j++){auto d=std::int64_t(a[j])-b[j];x+=d*d;}return x;}
struct Task{U at,serial;std::function<void()> fn;};
struct Later{bool operator()(const Task&a,const Task&b)const{return std::tie(a.at,a.serial)>std::tie(b.at,b.serial);}};
struct Query{Vec v{};std::vector<int> pages;std::vector<Score> scores;int consumed=0;U produced=0;};
struct Slot{bool busy=false,visible=false;int q=-1,page=-1;std::array<unsigned char,PS> bytes{};};
class Run {
  el::SimulationSession hbf;
#ifdef ANNS_CONCURRENT
  #ifdef ANNS_BANK
  BankAdapter hbm;
  #else
  OnlineHbm hbm;
  #endif
#else
  ph::hbm::HbmDevice hbm;
#endif
  std::array<Vec,N> db{};
  std::array<Query,2> queries{};
  std::vector<Slot> slots;
  std::deque<std::pair<int,int>> waiting;
  // Sidecar payload backing is addressed by the actual submitted byte address.
  // EventLab itself checks symbolic tokens, not these bytes.
  std::map<U,std::pair<int,U>> pending;
  std::priority_queue<Task,std::vector<Task>,Later> tasks;
  U serial=0,request=1000,now=0,origin=0,hbm_free=0,gpu_free=0;
  U gpu_ps,producer_ps,reads=0,writes=0,hbm_reads=0,done=0,peak=0,blocked=0;
  std::string mutation;
  static el::SimulationConfiguration config(U sense){el::SimulationConfiguration c;
#ifdef ANNS_CONCURRENT
    c.execution.core_bytes_per_ns=32;c.execution.core_propagation=el::Tick{1000};
#endif
    c.device.geometry.host_channels=1;c.execution.media_timing.sense=el::Tick{sense};
    c.execution.read_dispatch.wait=el::Tick{0};c.host.max_resident_fragments=512;return c;}
  static ph::hbm::HbmConfig hbm_config(){ph::hbm::HbmConfig c;c.capacity_bytes=1<<20;return c;}
  void log(const char* type,int q=-1,int slot=-1,int page=-1,U start=0,U end=0,U bytes=0){
    std::cout<<"{\"event\":\""<<type<<"\",\"t_ps\":"<<now<<",\"q\":"<<q<<",\"slot\":"<<slot
      <<",\"page\":"<<page<<",\"start_ps\":"<<start<<",\"end_ps\":"<<end<<",\"bytes\":"<<bytes<<"}\n";
  }
  void schedule(U t,std::function<void()> f){check(t>=now,"event in past");tasks.push({t,serial++,std::move(f)});}
  void memory(int q,int s,bool write,U addr,U bytes,std::function<void()> next){
#ifdef ANNS_CONCURRENT
    if(write)writes+=bytes;else hbm_reads+=bytes;
    bool accepted=hbm.submit(now,write,addr,bytes,[this,q,s,write,bytes,next](U start,U end){
      log(write?"hbm_write":"hbm_read",q,s,s<0?-1:slots[s].page,start,end,bytes);next();
    });
    check(accepted,"online HBM admission exhausted");
#else
    U start=std::max(now,hbm_free);
    auto receipt=hbm.issue(ph::PhysicalRequest{.id=std::to_string(serial++),.tier=ph::Tier::HBM,
      .op=write?ph::Op::Write:ph::Op::Read,.address_space=ph::AddressSpace::Physical,
      .arrival_ns=double(start)/1000.,.addr=addr,.bytes=bytes});
    U end=U(std::ceil(receipt.finish_ns*1000.));check(end>=start,"HBM time reversal");hbm_free=end;
    if(write)writes+=bytes;else hbm_reads+=bytes;
    log(write?"hbm_write":"hbm_read",q,s,s<0?-1:slots[s].page,start,end,bytes);
    schedule(end,std::move(next));
#endif
  }
  void compute(int q,int s,U duration,std::function<void()> next){
    U start=std::max(now,gpu_free),end=start+duration;gpu_free=end;
    log("compute",q,s,s<0?-1:slots[s].page,start,end);
    schedule(end,std::move(next));
  }
  void admit(){
    while(!waiting.empty()){
      auto it=std::find_if(slots.begin(),slots.end(),[](auto&s){return !s.busy;});
      if(it==slots.end()){blocked++;return;}
      int s=int(it-slots.begin());auto [q,p]=waiting.front();waiting.pop_front();
      check(now>=queries[q].produced,"request before producer");
      *it=Slot{};it->busy=true;it->q=q;it->page=p;
      U id=request++;reads+=PS;
      peak=std::max(peak,U(std::count_if(slots.begin(),slots.end(),[](auto&a){return a.busy;})));
      log("hbf_submit",q,s,p,0,0,PS);
      el::GlobalRequest r{el::GlobalRequestId{id},el::Op::Read,el::GlobalByteAddress{U(p)*PS},PS};
      if(mutation=="wrong_address")r.address.value=(r.address.value+PS)%(N*sizeof(Vec));
      pending.emplace(id,std::make_pair(s,r.address.value));
      r.expected_content=1;r.not_before=el::Tick{now};hbf.submit(r);
    }
  }
  void consume(int s){auto& slot=slots[s];check(slot.busy&&slot.visible,"consume before HBM visibility");
    int q=slot.q,p=slot.page;
    for(int j=0;j<PER;j++){Vec v;std::memcpy(v.data(),slot.bytes.data()+j*sizeof(Vec),sizeof(Vec));
      check(v==db[p*PER+j],"payload mismatch");queries[q].scores.emplace_back(distance(v,queries[q].v),p*PER+j);}
    log("consume",q,s,p);slot.busy=false;slot.visible=false;queries[q].consumed++;admit();
    if(queries[q].consumed==int(queries[q].pages.size())){
      memory(q,-1,true,65536+q*256,128,[this,q]{compute(q,-1,gpu_ps,[this,q]{finish(q);});});
    }
  }
  void returned(const el::GlobalCompletion& c){
    check(c.result.state==el::LogicalResult::Success,"HBF failure");
    if(c.result.id.value<1000)return;
    now=c.at.value;auto i=pending.find(c.result.id.value);check(i!=pending.end(),"unknown completion");
    auto [s,address]=i->second;pending.erase(i);auto q=slots[s].q,p=slots[s].page;
    log("hbf_complete",q,s,p,0,0,PS);
    if(mutation=="early_consume")consume(s);
    memory(q,s,true,U(s)*PS,PS,[this,s,q,p,address]{
      auto& slot=slots[s];check(slot.busy&&slot.page==p&&slot.q==q,"buffer overwritten during fill");
      std::memcpy(slot.bytes.data(),reinterpret_cast<const unsigned char*>(db.data())+address,PS);
      if(mutation=="corrupt_payload")slot.bytes[0]^=1;
      slot.visible=true;log("visible",q,s,p);
      memory(q,s,false,U(s)*PS,PS,[this,s,q]{compute(q,s,gpu_ps,[this,s]{consume(s);});});
    });
    hbf.request_yield();
  }
  void produce(int q){
    queries[q].produced=now;log("producer_done",q);
    // Four fixed IVF centroids, probe nearest two. Real integer L2, deterministic ties.
    std::vector<Score> coarse;
    for(int l=0;l<4;l++){Vec center;center.fill(l*100);coarse.emplace_back(distance(center,queries[q].v),l);}
    std::sort(coarse.begin(),coarse.end());
    for(int l=0;l<2;l++)for(int j=0;j<2;j++){int p=coarse[l].second*2+j;queries[q].pages.push_back(p);waiting.emplace_back(q,p);}
    admit();
  }
  void finish(int q){auto scores=queries[q].scores;std::sort(scores.begin(),scores.end());scores.resize(K);
    // Separate native reference consumes database vectors directly, not staged bytes.
    std::vector<Score> reference,gt;for(int id=0;id<N;id++){
      Score x{distance(db[id],queries[q].v),id};gt.push_back(x);
      if(std::find(queries[q].pages.begin(),queries[q].pages.end(),id/PER)!=queries[q].pages.end())reference.push_back(x);
    }
    std::sort(reference.begin(),reference.end());reference.resize(K);std::sort(gt.begin(),gt.end());gt.resize(K);
    check(scores==reference,"top-k differs from native IVF reference");int hits=0;for(auto x:scores)hits+=std::find(gt.begin(),gt.end(),x)!=gt.end();
    log("query_done",q);std::cout<<"{\"result_q\":"<<q<<",\"hits_at_10\":"<<hits<<",\"ids\":[";
    for(int j=0;j<K;j++)std::cout<<(j?",":"")<<scores[j].second;std::cout<<"]}\n";done++;
  }
public:
  Run(U sense,U compute_ps,int buffers,U delay,std::string fault):hbf(el::resolve_configuration(config(sense))),
#ifdef ANNS_CONCURRENT
    hbm(hbm_config(),1024,[this](U t,std::function<void()> f){schedule(t,std::move(f));},
        [this](U lane,U start,U end,U bytes){log("hbm_burst",int(lane),-1,-1,start,end,bytes);}),
#else
    hbm(hbm_config()),
#endif
    slots(buffers),gpu_ps(compute_ps),producer_ps(delay),mutation(std::move(fault)){
    check(buffers>=1&&buffers<=2&&gpu_ps>0&&producer_ps>0,"invalid fixture setting");
    for(int i=0;i<N;i++)for(int j=0;j<D;j++)db[i][j]=(i/64)*100+((i*17+j*13)%23)-11;
    queries[0].v=db[27];queries[1].v=db[172];
    hbf.set_completion_handler([this](const auto& c){returned(c);});
    if(const char* path=std::getenv("ANNS_CONFIG_OUT")){std::ofstream f(path);check(bool(f),"cannot save config");el::write_effective_configuration(f,hbf.configuration());}
  }
  void run(){
    // Install all eight pages through the backend's actual write lifecycle.
    for(int p=0;p<N/PER;p++)hbf.submit(el::GlobalRequest{el::GlobalRequestId{U(p+1)},el::Op::Write,el::GlobalByteAddress{U(p)*PS},PS,1});
    auto setup=hbf.advance_until_yield();check(setup.run.status==el::RunStatus::WaitingForInput&&setup.run.workload_success,"setup failed");
    origin=hbf.now().value+1000;now=origin;log("begin");
    for(int q=0;q<2;q++)schedule(origin+q*1000,[this,q]{log("arrival",q);memory(q,-1,false,32768+q*512,512,
      [this,q]{compute(q,-1,producer_ps,[this,q]{produce(q);});});});
    int guard=0;
    while(done<2){check(++guard<100000,"closed loop stalled");
      if(!tasks.empty()){
        U boundary=tasks.top().at;auto r=hbf.advance_before(el::Tick{boundary});
        if(r.run.status!=el::RunStatus::Paused&&r.run.status!=el::RunStatus::WaitingForInput)
          throw std::runtime_error("backend failed during bounded advance: "+r.run.explanation);
        if(r.feedback_yield)continue;
        now=boundary;check(hbf.now().value==now,"clock disagreement");
        while(!tasks.empty()&&tasks.top().at==now){auto task=tasks.top();tasks.pop();task.fn();}
      }else{auto r=hbf.advance_until_yield();if(!r.feedback_yield)throw std::runtime_error("backend cannot make progress: "+r.run.explanation);}
    }
    check(waiting.empty()&&pending.empty()&&tasks.empty(),"unfinished work");
#ifdef ANNS_CONCURRENT
    check(hbm.resident_bursts()==0,"HBM queue leak");
#endif
    check(std::none_of(slots.begin(),slots.end(),[](auto&s){return s.busy;}),"buffer leak");
    hbf.close_input();auto r=hbf.run_to_completion();check(r.run.status==el::RunStatus::Completed&&r.run.workload_success,"drain failed");
    check(reads==8*PS&&writes==reads+256&&hbm_reads==reads+1024,"byte accounting");
    std::cout<<"{\"status\":\"PASS\",\"scope\":\"CPU_FUNCTIONAL_UNCALIBRATED\",\"peak_slots\":"<<peak
      <<",\"blocked_admissions\":"<<blocked<<",\"hbf_bytes\":"<<reads<<",\"hbm_write_bytes\":"<<writes<<",\"hbm_read_bytes\":"<<hbm_reads<<"}\n";
  }
};
int main(int argc,char** argv){try{Run r(argc>1?std::stoull(argv[1]):100000,argc>2?std::stoull(argv[2]):10000,
  argc>3?std::stoi(argv[3]):2,argc>4?std::stoull(argv[4]):10000,argc>5?argv[5]:"");r.run();}
  catch(const std::exception&e){std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}}
