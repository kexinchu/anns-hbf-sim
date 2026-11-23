#include "read_recovery.hpp"
#include <iostream>
int main(){ReadRecovery h;std::string op;unsigned a,b,c,d;
 while(std::cin>>op>>a>>b>>c>>d){try{
  if(op=="issue")std::cout<<(h.issue(a,b)?"accepted":"blocked");
  else if(op=="response")std::cout<<h.response(a,b,c,d);
  else if(op=="stage")std::cout<<h.retry_stage(a);
  else if(op=="poll"){h.poll(a,b);std::cout<<"ok";}
  else if(op=="write")std::cout<<(h.writable(a)?"allowed":"blocked");
  else if(op=="refresh"){h.begin_refresh(a,b,c);std::cout<<"ok";}
  else if(op=="page"){h.page_written(a,b,c);std::cout<<"ok";}
  else throw std::invalid_argument("unknown action");
 }catch(const std::exception&){std::cout<<"invalid";}std::cout<<'\n';}
}
