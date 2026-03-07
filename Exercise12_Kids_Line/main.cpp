//
//  main.cpp
//  Drawing B&W balls
//
//  Created by Broos  Maenhout on 15/03/2018.
//  Copyright © 2018 Broos  Maenhout. All rights reserved.
//
//


#include "general.h"

personnel *MyActivityPtr;


int main(int argc, const char * argv[]) {
    
    MyActivityPtr=new personnel;
    srand(100);//time(NULL));
    MyActivityPtr->procedure();
    
    delete MyActivityPtr;
    
    return 0;
    
}

