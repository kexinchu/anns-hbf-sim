#include "race_backend.h"
#include <cuda_runtime.h>
#include <condition_variable>
#include <mutex>
#include <stdexcept>
#include <string>
namespace {
void ck(cudaError_t e){if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}
struct Slot{cudaStream_t stream;cudaEvent_t event;int* host;long long* out;std::mutex mutex;std::condition_variable cv;bool open=true;};
Slot slots[4];int* frames;
void CUDART_CB gate(void* p){auto&s=*static_cast<Slot*>(p);std::unique_lock<std::mutex> lock(s.mutex);s.cv.wait(lock,[&]{return s.open;});}
__global__ void distance(const int* p,long long* out){int k=threadIdx.x;long long sum=0;for(int j=0;j<32;j++){long long d=p[k*32+j]-3;sum+=d*d;}out[k]=sum;}
Slot& slot(int f){if(f<0||f>=4)throw std::invalid_argument("frame");return slots[f];}
void done(Slot&s){ck(cudaEventRecord(s.event,s.stream));ck(cudaEventSynchronize(s.event));}
}
extern "C" void race_init(){cudaDeviceProp p;ck(cudaGetDeviceProperties(&p,0));if(std::string(p.name)!="NVIDIA RTX A6000")throw std::runtime_error("wrong GPU");ck(cudaMalloc(&frames,16384));
 for(auto&s:slots){ck(cudaStreamCreateWithFlags(&s.stream,cudaStreamNonBlocking));ck(cudaEventCreateWithFlags(&s.event,cudaEventDisableTiming));ck(cudaMallocHost(&s.host,4096));ck(cudaMalloc(&s.out,256));}
 ck(cudaMemset(frames,0,16384));distance<<<1,32>>>(frames,slots[0].out);ck(cudaGetLastError());ck(cudaDeviceSynchronize());}
extern "C" void race_fill(int f,int value){auto&s=slot(f);for(int i=0;i<1024;i++)s.host[i]=value+i%17;ck(cudaMemcpyAsync(frames+f*1024,s.host,4096,cudaMemcpyHostToDevice,s.stream));done(s);}
extern "C" void race_start(int f,bool held){auto&s=slot(f);{std::lock_guard<std::mutex> lock(s.mutex);s.open=!held;}if(held)ck(cudaLaunchHostFunc(s.stream,gate,&s));distance<<<1,32,0,s.stream>>>(frames+f*1024,s.out);ck(cudaGetLastError());ck(cudaMemcpyAsync(s.host,s.out,256,cudaMemcpyDeviceToHost,s.stream));ck(cudaEventRecord(s.event,s.stream));}
extern "C" bool race_ready(int f){auto e=cudaEventQuery(slot(f).event);if(e==cudaErrorNotReady)return false;ck(e);return true;}
extern "C" void race_open(int f){auto&s=slot(f);{std::lock_guard<std::mutex> lock(s.mutex);s.open=true;}s.cv.notify_all();}
extern "C" void race_result(int f,long long* result){auto&s=slot(f);ck(cudaEventSynchronize(s.event));auto p=reinterpret_cast<long long*>(s.host);for(int i=0;i<32;i++)result[i]=p[i];}
extern "C" void race_copy(int f,int* data){auto&s=slot(f);ck(cudaMemcpyAsync(s.host,frames+f*1024,4096,cudaMemcpyDeviceToHost,s.stream));done(s);for(int i=0;i<1024;i++)data[i]=s.host[i];}
extern "C" void race_close(){for(int f=0;f<4;f++)race_open(f);for(auto&s:slots){ck(cudaStreamSynchronize(s.stream));ck(cudaFreeHost(s.host));ck(cudaFree(s.out));ck(cudaEventDestroy(s.event));ck(cudaStreamDestroy(s.stream));}ck(cudaFree(frames));}
