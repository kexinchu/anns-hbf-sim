#include "reset_device.hpp"
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
 ResetDevice device;race_init();std::string op;unsigned long long a,b,c;std::string mutation=argc>1?argv[1]:"";
 while(std::cin>>op>>a>>b>>c){std::string result="ok";long long value=0;std::vector<unsigned long long> coords;long long scores[32];bool gpu=false;
 try{
 if(op=="O")device.power_on();else if(op=="P")device.power_loss();else if(op=="A")device.advance(a);
 else if(op=="S")result=device.csr_write(a,b,c);else if(op=="C"){value=device.csr_read(a,b);if(mutation=="early_ready"&&b==16)value=1;}
 else if(op=="D")device.die_reset(a,b);else if(op=="E")device.erase(a);else if(op=="X")device.replace(a);
 else if(op=="W")result=device.program(a,b,c);else if(op=="L")result=device.deliver(a);
 else if(op=="M"){auto p=device.map(a);coords={p.channel,p.die,p.bank,p.block,p.page,p.byte_offset};if(mutation=="alias_die")coords[1]=0;}
 else if(op=="R"||op=="G"){auto r=device.read(a);result=r.first;value=r.second;if(mutation=="publish_unknown"&&result=="unknown"){result="known";value=99;}
  if(op=="G"&&result=="known"){race_fill(0,value);race_start(0,false);race_result(0,scores);gpu=true;}}
 else throw std::invalid_argument("action");
 }catch(const std::exception&){result="error";value=0;}
 std::cout<<"{\"result\":\""<<result<<"\",\"value\":"<<value<<",\"map\":[";for(unsigned i=0;i<coords.size();i++)std::cout<<(i?",":"")<<coords[i];std::cout<<"],\"scores\":[";if(gpu)for(int i=0;i<32;i++)std::cout<<(i?",":"")<<scores[i];std::cout<<"]}\n";
 }race_close();
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';race_close();return 1;}}
