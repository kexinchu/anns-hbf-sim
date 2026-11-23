#include "ucie_lifetime.hpp"
#include <iostream>
#include <sstream>
int main(){ucie::Pair p;std::string line;while(std::getline(std::cin,line)){std::istringstream s(line);std::string op;unsigned e=0,v=0;s>>op>>e>>v;bool ok=false;aou::Bytes data;
 try{if(op=="tick"){p.tick();ok=true;}else if(op=="req")ok=p.request(e,v);else if(op=="sts")ok=p.acknowledge(e);else if(op=="state")ok=p.transition(e,v);else if(op=="send")ok=p.send(e,{static_cast<unsigned char>(v)});else if(op=="launch")ok=p.launch(e);else if(op=="arrive")ok=p.arrive(e,v);else if(op=="queue_ack")ok=p.queue_ack(e);else if(op=="ack")ok=p.ack(e,v);else if(op=="replay")ok=p.replay(e);else if(op=="consume")ok=p.consume(e,data);else if(op=="clean")ok=p.cleanup(e);else if(op=="reset")ok=p.reset_exit();else throw std::invalid_argument("operation");
 std::cout<<ok<<' '<<(data.empty()?-1:int(data[0]))<<' '<<p.clock<<' '<<p.accepted<<' '<<p.dropped<<' '<<p.crc_errors<<' '<<p.duplicates<<' '<<p.discarded;
 for(unsigned i=0;i<2;i++){auto&q=p.ep[i];std::cout<<' '<<q.state<<' '<<q.req<<' '<<q.sts<<' '<<q.next<<' '<<q.expected<<' '<<q.retry.size()<<' '<<q.tx.size()<<' '<<q.rx.size()<<' '<<p.flight[i].size();}std::cout<<'\n';
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
}
