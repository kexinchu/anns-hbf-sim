#include "bank_hbm.hpp"
#include <iostream>
#include <map>
int main(){try{
 struct Input{std::uint64_t at,id,bank,row,write;};std::vector<Input> input;Input r;
 while(std::cin>>r.at>>r.id>>r.bank>>r.row>>r.write)input.push_back(r);
 if(!std::is_sorted(input.begin(),input.end(),[](auto&a,auto&b){return a.at<b.at;}))throw std::invalid_argument("unsorted arrivals");
 BankHbm model(4,8);std::size_t next=0;
 for(std::uint64_t tick=0;tick<10000;++tick){
  while(next<input.size()&&input[next].at==tick){auto q=input[next++];bool ok=model.submit(tick,q.id,q.bank,q.row,q.write);std::cout<<"["<<tick<<","<<q.id<<","<<q.bank<<","<<q.row<<",\""<<(ok?"ACCEPT":"REJECT")<<"\"]\n";}
  for(auto e:model.step(tick))std::cout<<"["<<e.tick<<","<<e.id<<","<<e.bank<<","<<e.row<<",\""<<e.op<<"\"]\n";
  if(next==input.size()&&!model.resident())return 0;
 }
 throw std::runtime_error("undrained simulation");
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
