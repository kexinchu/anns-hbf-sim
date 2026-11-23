#include "bank_adapter.hpp"
#include <queue>
#include <iostream>
#include <tuple>
int main(){using U=std::uint64_t;struct E{U t,id;std::function<void()> f;};
 auto cmp=[](const E&a,const E&b){return std::tie(a.t,a.id)>std::tie(b.t,b.id);};
 std::priority_queue<E,std::vector<E>,decltype(cmp)> q(cmp);U serial=0,now=0,done=0,bytes=0,bus=0;
 auto check=[](bool b){if(!b)throw std::runtime_error("adapter contract");};
 hbfsim::physical::hbm::HbmConfig config;config.capacity_bytes=1<<20;
 BankAdapter m(config,2,[&](U t,std::function<void()> f){check(t>=now);q.push({t,serial++,std::move(f)});},
 [&](U,U s,U e,U n){check(s==now&&s>=bus&&e>s);bus=e;bytes+=n;});
 auto cb=[&](U a,U e){check(e==now&&e>a);++done;};
 check(m.submit(0,false,63,2,cb)); // two bursts, one parent
 check(!m.submit(0,false,128,1,cb));check(m.resident_bursts()==2);
 while(!q.empty()){auto e=q.top();q.pop();now=e.t;e.f();}
 check(done==1&&bytes==128&&m.resident_bursts()==0);
 now+=100003;check(m.submit(now,true,64,64,cb));
 while(!q.empty()){auto e=q.top();q.pop();now=e.t;e.f();}
 check(done==2&&bytes==192&&m.resident_bursts()==0);
 for(auto [a,n]:std::vector<std::pair<U,U>>{{0,0},{1<<20,1},{(1<<20)-1,2}}){
  bool rejected=false;try{m.submit(now,false,a,n,cb);}catch(const std::invalid_argument&){rejected=true;}check(rejected);}
 check(q.empty());std::cout<<"PASS split parent, atomic capacity, idle clock, physical bytes, invalid ranges\n";
}
