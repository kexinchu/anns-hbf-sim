// Functional IVF2/4 fixture, actual CUDA distance/top-k. No performance claims.
#include <cuda_runtime.h>
#include "../src/read_recovery.hpp"
#include "../src/versioned_pages.hpp"
#include <algorithm>
#include <array>
#include <cstring>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>
void ck(cudaError_t e){if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}
void need(bool b,const char*s){if(!b)throw std::runtime_error(s);}
__global__ void distances(const int* data,const int* query,const int* ids,int n,long long* score){
 int i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=n)return;long long sum=0;
 for(int j=0;j<32;++j){long long d=data[i*32+j]-query[j];sum+=d*d;}score[i]=sum;
}
__global__ void topk(const long long* score,const int* ids,int n,int* out){
 for(int k=0;k<10;++k){int best=-1;for(int i=0;i<n;++i){bool used=false;for(int j=0;j<k;++j)used|=out[j]==i;
 if(!used&&(best<0||score[i]<score[best]||(score[i]==score[best]&&ids[i]<ids[best])))best=i;}out[k]=best;}
}
void log(const std::string& e,int p=-1,int value=0){std::cout<<"{\"event\":\""<<e<<"\",\"page\":"<<p<<",\"value\":"<<value<<"}\n";}
int main(int argc,char**argv){try{
 std::string mode=argc>1?argv[1]:"clean";cudaDeviceProp prop;ck(cudaGetDeviceProperties(&prop,0));need(std::string(prop.name)=="NVIDIA RTX A6000","wrong GPU");
 std::vector<int> backup(256*32),media;for(int i=0;i<256;++i)for(int j=0;j<32;++j)backup[i*32+j]=(i/64)*100+(i*17+j*13)%23-11;media=backup;
 ReadRecovery recovery;unsigned command=0;bool injected=false;std::vector<int> received;
 for(int q=0;q<2;++q){int qi=q?172:27;std::vector<std::pair<long long,int>> coarse;
 for(int l=0;l<4;++l){long long s=0;for(int j=0;j<32;++j){long long d=l*100-backup[qi*32+j];s+=d*d;}coarse.push_back({s,l});}std::sort(coarse.begin(),coarse.end());
 std::vector<int> ids;received.clear();
 for(int l=0;l<2;++l)for(int pp=0;pp<2;++pp){int page=coarse[l].second*2+pp;unsigned id=++command;
 need(recovery.issue(id,0),"admission");log("read_issue",page,id);
 unsigned status=0,info=0;bool valid=true;
 if(!injected&&mode!="clean"&&mode!="corrupt_gpu"&&mode!="early_publish"){
 injected=true;if(mode=="retry"||mode=="bad_stage"){status=6;info=3;valid=false;}
 else if(mode=="die"){status=9;info=1;valid=false;}
 else {status=mode=="cecc"?5:4;info=1;valid=status==5;if(!valid)media[page*1024]^=123;}
 }
 log("response",page,status);std::string action=recovery.response(id,status,info,valid);
 if(status==6){unsigned stage=recovery.retry_stage(id);if(mode=="bad_stage")stage^=1;
 need(stage==3,"transport retry stage mismatch");log("retry_send",page,stage);need(recovery.response(id,0,0,true)=="deliver","retry completion");}
 if(status==9){need(!recovery.writable(0),"die write escaped");need(!recovery.issue(++command,3),"die read escaped");
 need(recovery.issue(++command,4),"independent die stalled");recovery.response(command,0,0,true);log("other_die_done",page);
 recovery.poll(0,false);need(!recovery.writable(0),"early unblock");log("die_poll_busy",page);
 recovery.poll(0,true);log("die_poll_ready",page);need(recovery.issue(++command,0),"read after recovery");recovery.response(command,0,0,true);}
 if(status==4||status==5){log("refresh_begin",page);recovery.begin_refresh(0,8,mode!="no_backup");
 // Sequential full-page writes to transport media, read back before acknowledging.
 for(unsigned p=0;p<8;++p){if(mode=="refresh_fail"&&p==3){recovery.page_written(0,p,false);throw std::runtime_error("refresh program failure; quarantined");}
 std::copy(backup.begin()+p*1024,backup.begin()+(p+1)*1024,media.begin()+p*1024);
 need(std::equal(media.begin()+p*1024,media.begin()+(p+1)*1024,backup.begin()+p*1024),"refresh readback");recovery.page_written(0,p,true);log("refresh_page_verified",p);}
 log("refresh_complete",page);need(recovery.issue(++command,0),"refresh reread");recovery.response(command,0,0,true);}
 received.insert(received.end(),media.begin()+page*1024,media.begin()+(page+1)*1024);for(int j=0;j<32;++j)ids.push_back(page*32+j);log("publish",page);
 }
 int *d,*dq,*di,*out;long long* ds;ck(cudaMalloc(&d,2*4096));ck(cudaMalloc(&dq,128));ck(cudaMalloc(&di,ids.size()*4));ck(cudaMalloc(&ds,ids.size()*8));ck(cudaMalloc(&out,40));
 cudaStream_t stream;cudaEvent_t done;ck(cudaStreamCreateWithFlags(&stream,cudaStreamNonBlocking));ck(cudaEventCreateWithFlags(&done,cudaEventDisableTiming));
 ck(cudaMemcpy(dq,backup.data()+qi*32,128,cudaMemcpyHostToDevice));ck(cudaMemcpy(di,ids.data(),ids.size()*4,cudaMemcpyHostToDevice));
 VersionedPages pages;
 if(mode=="corrupt_gpu")received[0]^=511;
 for(int offset=0;offset<int(ids.size());offset+=32){int page=ids[offset]/32,ticket=offset+1;
  need(pages.begin(ticket,page)=="accepted","frame admission");int f=pages.fills.at(ticket).frame;
  if(mode=="early_publish")need(pages.acquire(ticket,page)=="acquired","device data not visible before H2D completion");
  ck(cudaMemcpyAsync(d+f*1024,received.data()+offset*32,4096,cudaMemcpyHostToDevice,stream));
  ck(cudaEventRecord(done,stream));ck(cudaEventSynchronize(done));need(pages.publish(ticket,cudaEventQuery(done)==cudaSuccess)=="ready","fill event permit");log("h2d_complete",page);
  need(pages.acquire(ticket,page)=="acquired","consume permit");
  distances<<<1,32,0,stream>>>(d+f*1024,dq,di+offset,32,ds+offset);ck(cudaGetLastError());
  ck(cudaEventRecord(done,stream));ck(cudaEventSynchronize(done));need(pages.release(ticket,cudaEventQuery(done)==cudaSuccess)=="released","consumer event permit");
  need(pages.evict(page)=="evicted","frame reclamation");
 }
 topk<<<1,1,0,stream>>>(ds,di,ids.size(),out);ck(cudaGetLastError());ck(cudaStreamSynchronize(stream));log("gpu_complete",q);
 ck(cudaEventDestroy(done));ck(cudaStreamDestroy(stream));
 std::vector<long long> score(ids.size());std::array<int,10> index;ck(cudaMemcpy(score.data(),ds,score.size()*8,cudaMemcpyDeviceToHost));ck(cudaMemcpy(index.data(),out,40,cudaMemcpyDeviceToHost));
 std::cout<<"{\"query\":"<<q<<",\"candidates\":[";for(size_t i=0;i<ids.size();++i)std::cout<<(i?",":"")<<"["<<ids[i]<<","<<score[i]<<"]";
 std::cout<<"],\"topk\":[";for(int k=0;k<10;++k)std::cout<<(k?",":"")<<ids[index[k]];std::cout<<"]}\n";
 ck(cudaFree(d));ck(cudaFree(dq));ck(cudaFree(di));ck(cudaFree(ds));ck(cudaFree(out));
 }
 std::cout<<"{\"status\":\"PASS\",\"scope\":\"CUDA_FUNCTIONAL_SYNTHETIC_HBF_TRANSPORT\",\"performance_ready\":false}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
