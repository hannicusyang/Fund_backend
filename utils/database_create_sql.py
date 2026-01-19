#fund_basic_info
"""
create table fund_db.fund_basic_info
(
    fund_code   text     null,
    pinyin_abbr text     null,
    fund_name   text     null,
    fund_type   text     null,
    pinyin_full text     null,
    update_time datetime null
);
"""


#fund_estimation
"""
create table fund_db.fund_estimation
(
    id                    int unsigned auto_increment
        primary key,
    fund_code             varchar(20)    not null,
    fund_name             varchar(255)   not null,
    estimation_date       date           not null comment '估算所针对的日期 (T日)',
    last_nav_date         date           null comment '上一交易日净值日期 (T-1日)',
    estimated_nav         decimal(18, 6) null,
    estimated_growth_rate decimal(10, 4) null,
    published_nav         decimal(18, 6) null,
    published_growth_rate decimal(10, 4) null,
    estimation_bias       decimal(10, 4) null,
    last_nav              decimal(18, 6) null comment 'T-1日单位净值',
    fetch_time            datetime       not null
);

create index idx_estimation_date
    on fund_db.fund_estimation (estimation_date);

create index idx_fetch_time
    on fund_db.fund_estimation (fetch_time);

create index idx_fund_code
    on fund_db.fund_estimation (fund_code);



"""


#fund_holding
"""
create table fund_db.fund_holdings
(
    id                bigint auto_increment
        primary key,
    fund_code         varchar(10)    not null,
    stock_code        varchar(10)    not null,
    stock_name        varchar(50)    not null,
    proportion_of_nav decimal(5, 2)  null,
    shares_held       decimal(12, 2) null,
    market_value      decimal(14, 2) null,
    quarter           varchar(20)    not null,
    report_date       date           null,
    created_at        datetime       null,
    constraint uk_fund_stock_quarter
        unique (fund_code, stock_code, quarter)
);


"""


#fund_nav_history
"""

create table fund_db.fund_nav_history
(
    fund_code         varchar(20)    not null comment '基金代码',
    nav_date          date           not null comment '净值日期',
    fund_name         varchar(255)   not null comment '基金简称',
    net_value         decimal(18, 6) null comment '单位净值',
    daily_growth_rate decimal(10, 4) null comment '日增长率 (%)',
    update_time       datetime       null comment '数据更新时间',
    primary key (fund_code, nav_date)
);

create index idx_fund_code
    on fund_db.fund_nav_history (fund_code);

create index idx_nav_date
    on fund_db.fund_nav_history (nav_date);


"""

#fund_open_rank_all
"""
create table fund_db.fund_open_rank_all
(
    id                          int auto_increment
        primary key,
    `rank`                      int          null,
    fund_code                   varchar(20)  not null,
    fund_name                   varchar(100) not null,
    date                        varchar(10)  null,
    net_value                   float        null,
    accumulated_net_value       float        null,
    daily_growth_rate           float        null,
    weekly_growth_rate          float        null,
    monthly_1_growth_rate       float        null,
    monthly_3_growth_rate       float        null,
    monthly_6_growth_rate       float        null,
    yearly_1_growth_rate        float        null,
    yearly_2_growth_rate        float        null,
    yearly_3_growth_rate        float        null,
    ytd_growth_rate             float        null,
    since_inception_growth_rate float        null,
    custom_growth_rate          float        null,
    fee_rate                    float        null,
    is_checked                  tinyint(1)   null,
    update_time                 datetime     null
);

create index ix_fund_open_rank_all_fund_code
    on fund_db.fund_open_rank_all (fund_code);

"""


#fund_watchlist
"""
create table fund_db.fund_watchlist
(
    id        bigint auto_increment
        primary key,
    user_id   varchar(36) default 'default'         not null comment '用户ID，单用户系统可设为 default',
    fund_code varchar(10)                           not null comment '基金代码，如 000001',
    added_at  datetime    default CURRENT_TIMESTAMP null comment '加入时间',
    constraint uk_user_fund
        unique (user_id, fund_code)
)
    comment '用户基金观察清单';

create index idx_added_at
    on fund_db.fund_watchlist (added_at);

create index idx_fund_code
    on fund_db.fund_watchlist (fund_code);

create index idx_user_id
    on fund_db.fund_watchlist (user_id);

"""


#trading_day
"""
create table fund_db.trading_day
(
    trade_date date not null
        primary key
);


"""



