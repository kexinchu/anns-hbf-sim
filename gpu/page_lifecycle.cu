#include <cuda_runtime.h>
#include "../src/versioned_pages.hpp"
#include <condition_variable>
#include <mutex>
#include <memory>
#include <vector>
#include <iostream>
#include <sstream>
#include <stdexcept>
void ck(cudaError_t e){if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}
struct Gate {std::mutex mutex;std::condition_variable cv;bool open=false;
 void release(){std::lock_guard<std::mutex> l(mutex);open=true;cv.notify_all();}
 static void CUDART_CB wait(void*p){auto&g=*static_cast<Gate*>(p);std::unique_lock<std::mutex> l(g.mutex);g.cv.wait(l,[&]{return g.open;});}};
struct Work {cudaStream_t stream;cudaEvent_t event;Gate gate;void* host=nullptr;long long* output=nullptr;
 Work(){ck(cudaStreamCreateWithFlags(&stream,cudaStreamNonBlocking));ck(cudaEventCreateWithFlags(&event,cudaEventDisableTiming));ck(cudaMallocHost(&host,4096));ck(cudaMalloc(&output,42*8));}
 void start(bool hold){if(hold)ck(cudaLaunchHostFunc(stream,Gate::wait,&gate));else gate.release();}
 bool ready(bool wait){if(wait)ck(cudaEventSynchronize(event));auto e=cudaEventQuery(event);if(e==cudaErrorNotReady)return false;ck(e);return true;}
 ~Work(){gate.release();cudaStreamSynchronize(stream);cudaEventDestroy(event);cudaStreamDestroy(stream);cudaFreeHost(host);if(output)cudaFree(output);}};
__global__ void score(const int* page,long long*out){int i=threadIdx.x;long long sum=0;for(int j=0;j<32;++j){long long d=page[i*32+j]-3;sum+=d*d;}out[i]=sum;}
__global__ void rank10(long long*out){for(int k=0;k<10;++k){int best=-1;for(int i=0;i<32;++i){bool used=false;for(int j=0;j<k;++j)used|=out[32+j]==i;if(!used&&(best<0||out[i]<out[best]||(out[i]==out[best]&&i<best)))best=i;}out[32+k]=best;}}
int main(int argc,char**argv){try{
 bool corrupt=argc>1&&std::string(argv[1])=="corrupt_fill";
 cudaDeviceProp prop;ck(cudaGetDeviceProperties(&prop,0));if(std::string(prop.name)!="NVIDIA RTX A6000")throw std::runtime_error("wrong GPU");
 VersionedPages m;int* device;ck(cudaMalloc(&device,8192));
 // Allocate all CUDA resources before any held stream: cudaMalloc may synchronize.
 std::vector<std::unique_ptr<Work>> pool;for(int i=0;i<64;++i)pool.push_back(std::make_unique<Work>());size_t next=0;
 auto work=[&](bool hold){if(next==pool.size())throw std::runtime_error("work pool exhausted");auto w=pool[next++].get();w->start(hold);return w;};
 // Materialize kernels before gated streams (CUDA lazy loading may synchronize).
 ck(cudaMemset(device,0,8192));score<<<1,32>>>(device,pool[0]->output);ck(cudaGetLastError());rank10<<<1,1>>>(pool[0]->output);ck(cudaGetLastError());ck(cudaDeviceSynchronize());
 std::map<int,Work*> fills,leases,writes;std::map<int,std::vector<int>> backing;
 std::string line;while(std::getline(std::cin,line)){std::istringstream in(line);std::string op;int a=0,b=0,c=0,d=0;in>>op>>a>>b>>c>>d;std::string result="invalid";std::vector<long long> answer;
 if(op=="fill"){
  if(fills.count(a))result="invalid";else result=m.begin(a,b);
  if(result=="accepted"){auto w=work(d);auto p=static_cast<int*>(w->host);for(int i=0;i<1024;++i)p[i]=(corrupt?c+11:c)+i%17;
   int frame=m.fills.at(a).frame;ck(cudaMemcpyAsync(device+frame*1024,p,4096,cudaMemcpyHostToDevice,w->stream));ck(cudaEventRecord(w->event,w->stream));fills.emplace(a,std::move(w));}
 }else if(op=="publish"){
  if(m.fills.count(a))result=m.publish(a,fills.at(a)->ready(b));
 }else if(op=="refresh")result=m.refresh(a);
 else if(op=="acquire"){
  if(leases.count(a))result="invalid";else result=m.acquire(a,b);
  if(result=="acquired"){auto w=work(c);int frame=m.leases.at(a).frame;
   score<<<1,32,0,w->stream>>>(device+frame*1024,w->output);ck(cudaGetLastError());rank10<<<1,1,0,w->stream>>>(w->output);ck(cudaGetLastError());
   ck(cudaMemcpyAsync(w->host,w->output,42*8,cudaMemcpyDeviceToHost,w->stream));ck(cudaEventRecord(w->event,w->stream));leases.emplace(a,std::move(w));}
 }else if(op=="release"){
  if(m.leases.count(a)){bool ready=leases.at(a)->ready(b);result=m.release(a,ready);if(ready){auto p=static_cast<long long*>(leases.at(a)->host);answer.assign(p,p+42);}}
 }else if(op=="dirty")result=m.dirty(a);
 else if(op=="evict")result=m.evict(a);
 else if(op=="writeback"){
  result=m.writeback(a);if(result=="writing"){auto w=work(b);int frame=m.resident(a);ck(cudaMemcpyAsync(w->host,device+frame*1024,4096,cudaMemcpyDeviceToHost,w->stream));ck(cudaEventRecord(w->event,w->stream));writes[a]=std::move(w);}
 }else if(op=="commit"){
  if(writes.count(a)){bool ready=writes.at(a)->ready(b);result=m.written(a,ready,c);if(result=="committed"){auto p=static_cast<int*>(writes.at(a)->host);backing[a]=std::vector<int>(p,p+1024);}}
 }else if(op=="block")result=m.block(a,b);
 else if(op=="open"){
  auto& group=a==0?fills:a==1?leases:writes;auto i=group.find(b);if(i!=group.end()){i->second->gate.release();result="opened";}
 }
 std::cout<<"{\"result\":\""<<result<<"\",\"frames\":[";for(int i=0;i<2;++i){auto&f=m.frames[i];std::cout<<(i?",":"")<<"["<<f.page<<","<<f.generation<<",\""<<f.state<<"\","<<f.pins<<","<<(f.dirty?1:0)<<"]";}std::cout<<"],\"gpu\":[";for(size_t i=0;i<answer.size();++i)std::cout<<(i?",":"")<<answer[i];
 std::cout<<"],\"backing\":[";bool comma=false;for(auto&[page,data]:backing){std::cout<<(comma?",":"")<<"["<<page<<","<<data.front()<<","<<data.back()<<"]";comma=true;}std::cout<<"]}\n";
 }
 // Release every host gate before joining any stream, including negative cases.
 for(auto*group:{&fills,&leases,&writes})for(auto&[id,w]:*group)w->gate.release();
 fills.clear();leases.clear();writes.clear();pool.clear();ck(cudaFree(device));
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
