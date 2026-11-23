#include "page_backend.h"
#include <cuda_runtime.h>
#include <stdexcept>
#include <string>
namespace {
int* frames;int* query;long long* scores;cudaStream_t stream;cudaEvent_t event;
void ck(cudaError_t e){if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}
__global__ void score(const int* p,const int* q,long long* out){int i=threadIdx.x;long long s=0;for(int j=0;j<32;j++){long long d=p[i*32+j]-q[j];s+=d*d;}out[i]=s;}
void finish(){ck(cudaEventRecord(event,stream));ck(cudaEventSynchronize(event));ck(cudaEventQuery(event));}
}
extern "C" void cuda_pages_init(){cudaDeviceProp p;ck(cudaGetDeviceProperties(&p,0));if(std::string(p.name)!="NVIDIA RTX A6000")throw std::runtime_error("wrong GPU");ck(cudaMalloc(&frames,8192));ck(cudaMalloc(&query,128));ck(cudaMalloc(&scores,256));ck(cudaStreamCreateWithFlags(&stream,cudaStreamNonBlocking));ck(cudaEventCreateWithFlags(&event,cudaEventDisableTiming));}
extern "C" void cuda_page_fill(int f,const void* b){if(f<0||f>=2)throw std::runtime_error("bad frame");ck(cudaMemcpyAsync(frames+f*1024,b,4096,cudaMemcpyHostToDevice,stream));finish();}
extern "C" void cuda_page_score(int f,const int* q,long long* out){if(f<0||f>=2)throw std::runtime_error("bad frame");ck(cudaMemcpyAsync(query,q,128,cudaMemcpyHostToDevice,stream));score<<<1,32,0,stream>>>(frames+f*1024,query,scores);ck(cudaGetLastError());ck(cudaMemcpyAsync(out,scores,256,cudaMemcpyDeviceToHost,stream));finish();}
extern "C" void cuda_pages_close(){ck(cudaStreamDestroy(stream));ck(cudaEventDestroy(event));ck(cudaFree(frames));ck(cudaFree(query));ck(cudaFree(scores));}

extern "C" void cuda_page_readback(int f,void* b){if(f<0||f>=2)throw std::runtime_error("bad frame");ck(cudaMemcpyAsync(b,frames+f*1024,4096,cudaMemcpyDeviceToHost,stream));finish();}
