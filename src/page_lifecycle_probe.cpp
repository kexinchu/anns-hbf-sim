#include "versioned_pages.hpp"
#include <vector>
#include <iostream>
#include <sstream>
struct Work {int frame,value;bool held;std::uint64_t token=0,epoch=0;};
int main(int argc,char**argv){VersionedPages m;std::map<int,Work> fills,leases,writes;std::map<int,int> values,backing;
 bool corrupt=argc>1&&std::string(argv[1])=="corrupt_fill";std::string line;
 while(std::getline(std::cin,line)){std::istringstream in(line);std::string op;int a=0,b=0,c=0,d=0;in>>op>>a>>b>>c>>d;std::string result="invalid";std::vector<long long> answer;
 if(op=="fill"){if(!fills.count(a))result=m.begin(a,b);if(result=="accepted"){int i=m.fills.at(a).frame;values[i]=c+(corrupt?11:0);fills[a]={i,values[i],bool(d)};}}
 else if(op=="publish"){if(m.fills.count(a))result=m.publish(a,!fills.at(a).held);}
 else if(op=="refresh")result=m.refresh(a);
 else if(op=="acquire"){if(!leases.count(a))result=m.acquire(a,b);if(result=="acquired"){int i=m.leases.at(a).frame;leases[a]={i,values[i],bool(c)};}}
 else if(op=="release"){if(m.leases.count(a)){result=m.release(a,!leases.at(a).held);if(result=="released"){
 int value=leases.at(a).value;for(int i=0;i<32;++i){long long sum=0;for(int j=0;j<32;++j){long long delta=value+(i*32+j)%17-3;sum+=delta*delta;}answer.push_back(sum);}
 for(int k=0;k<10;++k){int best=-1;for(int i=0;i<32;++i){bool used=false;for(int j=0;j<k;++j)used|=answer[32+j]==i;if(!used&&(best<0||answer[i]<answer[best]||(answer[i]==answer[best]&&i<best)))best=i;}answer.push_back(best);}}}}
 else if(op=="dirty")result=m.dirty(a);
 else if(op=="evict")result=m.evict(a);
 else if(op=="writeback"){result=m.writeback(a);if(result=="writing"){int i=m.resident(a);auto t=m.writebacks.at(a);writes[a]={i,values[i],bool(b),t.token,t.epoch};}}
 else if(op=="commit"){if(writes.count(a)){result=m.written(a,writes.at(a).token,writes.at(a).epoch,!writes.at(a).held,c);if(result=="committed")backing[a]=writes.at(a).value;}}
 else if(op=="ack"){if(writes.count(a)){result=m.written(a,b,c,!writes.at(a).held,d);if(result=="committed")backing[a]=writes.at(a).value;}else result="stale_ack";}
 else if(op=="block")result=m.block(a,b);
 else if(op=="open"){auto&g=a==0?fills:a==1?leases:writes;if(g.count(b)){g.at(b).held=false;result="opened";}}
 std::cout<<"{\"result\":\""<<result<<"\",\"frames\":[";for(int i=0;i<2;++i){auto&f=m.frames[i];std::cout<<(i?",":"")<<"["<<f.page<<","<<f.generation<<",\""<<f.state<<"\","<<f.pins<<","<<(f.dirty?1:0)<<"]";}std::cout<<"],\"gpu\":[";for(size_t i=0;i<answer.size();++i)std::cout<<(i?",":"")<<answer[i];std::cout<<"],\"backing\":[";bool comma=false;for(auto&[page,value]:backing){std::cout<<(comma?",":"")<<"["<<page<<","<<value<<","<<value+1023%17<<"]";comma=true;}std::cout<<"]}\n";
 }
}
