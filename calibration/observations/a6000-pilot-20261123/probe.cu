// Dependent-load observation; NOT HBM/bank timing calibration.
#include <cuda_runtime.h>
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <numeric>
#include <random>
#include <stdexcept>
#include <vector>
void ck(cudaError_t e){if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}
__global__ void chase(const unsigned* p,unsigned steps,unsigned* result,unsigned long long* cycles){
 unsigned x=0;auto begin=clock64();
 for(unsigned i=0;i<steps;++i){const unsigned* a=p+size_t(x)*16;asm volatile("ld.global.cg.u32 %0, [%1];":"=r"(x):"l"(a):"memory");}
 *cycles=clock64()-begin;*result=x;
}
int main(){try{ck(cudaSetDevice(0));cudaDeviceProp prop;ck(cudaGetDeviceProperties(&prop,0));
 if(std::string(prop.name)!="NVIDIA RTX A6000")throw std::runtime_error("wrong GPU");
 std::cout<<"{\"device\":\""<<prop.name<<"\",\"l2_bytes\":"<<prop.l2CacheSize<<",\"scope\":\"GDDR6_DEPENDENT_LOAD_ONLY\",\"performance_ready\":false}\n";
 for(unsigned nodes:{262144u,1048576u}){
  std::vector<unsigned> order(nodes),data(size_t(nodes)*16);std::iota(order.begin(),order.end(),0);std::mt19937 rng(173);
  std::shuffle(order.begin(),order.end(),rng);for(unsigned i=0;i<nodes;++i)data[size_t(order[i])*16]=order[(i+1)%nodes];
  unsigned *p,*out;unsigned long long *cy;ck(cudaMalloc(&p,data.size()*4));ck(cudaMalloc(&out,4));ck(cudaMalloc(&cy,8));
  ck(cudaMemcpy(p,data.data(),data.size()*4,cudaMemcpyHostToDevice));
  cudaEvent_t a,b;ck(cudaEventCreate(&a));ck(cudaEventCreate(&b));
  for(int sample=-1;sample<7;++sample){unsigned steps=65536,expected=0;for(unsigned i=0;i<steps;++i)expected=data[size_t(expected)*16];
   ck(cudaEventRecord(a));chase<<<1,1>>>(p,steps,out,cy);ck(cudaGetLastError());ck(cudaEventRecord(b));ck(cudaEventSynchronize(b));
   float ms;ck(cudaEventElapsedTime(&ms,a,b));unsigned got;unsigned long long cycles;
   ck(cudaMemcpy(&got,out,4,cudaMemcpyDeviceToHost));ck(cudaMemcpy(&cycles,cy,8,cudaMemcpyDeviceToHost));
   if(got!=expected)throw std::runtime_error("pointer chain mismatch");
   std::cout<<"{\"bytes\":"<<data.size()*4<<",\"sample\":"<<sample<<",\"steps\":"<<steps<<",\"elapsed_ms\":"<<ms<<",\"sm_cycles\":"<<cycles<<",\"verified\":true}\n";
  }
  ck(cudaEventDestroy(a));ck(cudaEventDestroy(b));ck(cudaFree(p));ck(cudaFree(out));ck(cudaFree(cy));
 }
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
