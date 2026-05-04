//
//  Helper.cpp
//  projestSMA
//
//  Created by Tine Meersman on 09/02/2022.
//  Copyright © 2022 Tine Meersman. All rights reserved.
//
#include "Helper.hpp"
#include <stdio.h>
#include <string>
#include <fstream>
#include <random>

double Exponential_distribution(double lambda){
    float j1 = float (rand()%1000)/1000;
    if (j1 == 0) j1 += 0.0001;
    float j2 = -log(j1)/lambda;
    return j2;
}


int Poisson_distribution(double lambda){
    float k, L, j1, j2, j3;
    int p;
    j1 = float (rand()%1000)/1000;
    k = 0;
    L = exp(-lambda);
    j3 = 0;
    do{
        j2 = L * pow(lambda, k);
        p = 1;
        for (int i6 = 0; i6 <= k; i6++){
            if (i6 == 0)
            p = 1;
        else
            p *= i6;
        }
        j2 /= p;
        j3 += j2;
        k++;
    } while (j1 >= j3);
    
    return k-1;
}

double Normal_distribution(double mean, double stdev){
    // TO MODEL BASED ON CUMULATIVE DENSITY FUNCTION OF NORMAL DISTRIBUTION BASED ON BOOK OF SHELDON ROSS, Simulation, The polar method, p80.
    
    float v1, v2, t;
    double x;
    do{
        v1 = float (rand()%1000)*2;
        v1 /= 1000;
        v1 -= 1;
        v2 = float (rand()%1000)*2;
        v2 /= 1000;
        v2 -= 1;
        t=v1*v1+v2*v2;
    }
    while(t>=1||t==0);
    float multiplier = sqrt(-2*log(t)/t);
    x = v1 * multiplier * stdev + mean;
    return x;
}

int Bernouilli_distribution(double prob){
    float j1 = rand()%1000/1000;
    if (j1 < prob)
        return 0;
    else
        return 1;
}

int Uniform_distribution(double a, double b){
    float j1 = rand()%1000/1000;
    return (int) a + (b-a) * j1;
}


int Triangular_distribution(int a, int b, int c){
    float mean, stdev,x, L;
    
    mean = (a+b+c)/3;
    stdev = (pow(a,2)+pow(b,2)+pow(c,2)-a*b-a*c-b*c)/18;
    stdev = sqrt(stdev);
    float j1 = float (rand()%1000)/1000;
    x = a;
    
    do{
        if (x <= b)
        L = pow((x-a),2)/((c-a)*(b-a));
    else
        L = 1-(pow(c-x,2)/((c-a)*(c-b)));
        x++;
    } while (j1 >= L);
    
    return x-1;
}


