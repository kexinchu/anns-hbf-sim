from pathlib import Path
s=Path('src/paper_curve_probe.cpp').read_text()
s=s.replace('argc!=5','argc!=6').replace('Geometry g{16','const unsigned mocs=std::stoul(argv[5]);\n Geometry g{16').replace('desc(g,{256,8,false,true},{256,','desc(g,{mocs,8,false,true},{mocs,')
s=s.replace('d.set_trace([&](const DeviceTrace&t){if(std::string(t.action)=="sense-issue")++senses;});','unsigned busy=0,peak_busy=0; d.set_trace([&](const DeviceTrace&t){if(std::string(t.action)=="sense-issue"){++senses;++busy;peak_busy=std::max(peak_busy,busy);}if(std::string(t.action)=="sense-finish"){if(!busy)throw std::logic_error("unbalanced sense");--busy;}});')
s=s.replace('if(done!=pages.size()','std::cerr<<"peak_busy_banks="<<peak_busy<<" remaining="<<busy<<" mocs="<<mocs<<"\\n";\n if(busy||done!=pages.size()')
Path('/tmp/credit_probe.cpp').write_text(s)
