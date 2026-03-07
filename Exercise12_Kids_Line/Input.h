//
//  Input.h
//  MarkovChain - Galton-Watson
//
//  Created by Broos  Maenhout on 22/09/2017.
//  Copyright © 2017 Broos  Maenhout. All rights reserved.
//

#ifndef Input_h
#define Input_h


#endif /* Input_h */




class personnel{
    
private:
    
public:
    
#define max(a,b) (((a)>(b)?(a):(b)))
#define min(a,b) (((a)>(b)?(b):(a)))
#define maxperiod  200
    
    FILE *file1;
    
    
    /* COUNTER */
    int i1, i2, i6, y, i0;
    double j1, j2, j3;
    double l1, a1;
    int K, s0, number_runs;
    
    double sum;
    double running_average;
    int offspring;
    
    int b, w;
    int w_selected;
    double average;
    double variance, total_variance;
    int count_draws, total_draws;
    int stack[6];
    int order[6];
    int count_success;
    char naam[300];
    /* constructor/destructor */
    personnel();
    
    ~personnel();
    
    int Poisson_distribution(double lambda);
    int Bernouilli_distribution(double prob);
    int Uniform_distribution(double a, double b);
    int Normal_distribution(double mean, double stdev);
    int Triangular_distribution(int a, int b, int c);
    void procedure();
    void init();


    
};

