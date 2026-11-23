#pragma once
// AoU 0.8 Appendix D, MSB-first fields; only the explicitly supported HBF subset.
#include <array>
#include <cstdint>
#include <vector>
#include <stdexcept>
namespace aou {
using Bytes=std::vector<std::uint8_t>;
struct Bits {
 Bytes b;std::size_t at=0;
 explicit Bits(std::size_t bytes):b(bytes){} explicit Bits(Bytes bytes):b(std::move(bytes)){}
 void put(unsigned n,std::uint64_t v){if(n<64&&(v>>n))throw std::invalid_argument("field width");if(at+n>b.size()*8)throw std::invalid_argument("length");for(unsigned i=n;i;i--,at++)b[at/8]|=((v>>(i-1))&1)<<(7-at%8);}
 std::uint64_t get(unsigned n){if(at+n>b.size()*8)throw std::invalid_argument("length");std::uint64_t v=0;while(n--){v=(v<<1)|((b[at/8]>>(7-at%8))&1);++at;}return v;}
 void zero(unsigned n){if(get(n))throw std::invalid_argument("reserved bits");}
};
struct Message {unsigned kind=0,rp=0,id=0,user=0,sync=0,count=0,status=0;std::uint64_t address=0;std::array<std::uint8_t,64> data{};};
inline Bytes encode(const Message&m){
 if(m.kind==2){Bits x(15);x.put(4,2);x.put(2,m.rp);x.put(2,0);x.put(9,m.user);x.put(3,0);x.put(14,m.id);x.put(3,6);x.put(3,0);x.put(8,0);x.put(8,0);x.put(8,m.sync);x.put(56,m.address);return x.b;}
 if(m.kind==4){Bits x(70);x.put(4,4);x.put(2,m.rp);x.put(2,1);x.put(9,m.user);x.put(3,0);x.put(14,m.id);x.put(3,m.status);x.put(1,1);x.put(2,0);for(auto b:m.data)x.put(8,b);x.put(8,m.sync);return x.b;}
 if(m.kind==5){Bits x(5);x.put(4,5);x.put(2,m.rp);x.put(2,m.sync>>6);x.put(9,m.user);x.put(3,(m.sync>>3)&7);x.put(14,m.id);x.put(3,m.status);x.put(3,m.sync&7);return x.b;}
 if(m.kind==0){Bits x(5);x.put(4,0);x.put(3,7);x.put(15,0);x.put(2,m.rp);x.put(8,m.count);x.put(8,m.sync);return x.b;}
 throw std::invalid_argument("unsupported message");
}
inline Message decode(const Bytes& b){Bits x(b);Message m;m.kind=x.get(4);
 if(m.kind==0){if(b.size()!=5||x.get(3)!=7)throw std::invalid_argument("unsupported misc");x.zero(15);m.rp=x.get(2);m.count=x.get(8);m.sync=x.get(8);return m;}
 m.rp=x.get(2);
 if(m.kind==2){if(b.size()!=15)throw std::invalid_argument("length");x.zero(2);m.user=x.get(9);x.zero(3);m.id=x.get(14);if(x.get(3)!=6)throw std::invalid_argument("unsupported size");x.zero(3);x.zero(8);x.zero(8);m.sync=x.get(8);m.address=x.get(56);return m;}
 if(m.kind==4){if(b.size()!=70||x.get(2)!=1)throw std::invalid_argument("unsupported read data");m.user=x.get(9);x.zero(3);m.id=x.get(14);m.status=x.get(3);if(x.get(1)!=1)throw std::invalid_argument("unsupported multibeat");x.zero(2);for(auto&v:m.data)v=x.get(8);m.sync=x.get(8);return m;}
 if(m.kind==5){if(b.size()!=5)throw std::invalid_argument("length");m.sync=x.get(2)<<6;m.user=x.get(9);m.sync|=x.get(3)<<3;m.id=x.get(14);m.status=x.get(3);m.sync|=x.get(3);return m;}
 throw std::invalid_argument("unsupported message");
}
}
