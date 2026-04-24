rm(list = ls())

library(data.table)
library(stringr)
library(survminer)
library(survival)
library(ggplot2)

################################################################################
# 1. 경로 및 폴더 구조 정의
# project폴더 - data - analysis폴더 - 병원별데이터
#             - result
################################################################################

cohort_id <- "cohortId" #v2120
# cohort_id <- "cohortDefinitionId" #v276

# (1) 경로 세팅
base_path <- "C:/Users/adam/Desktop/차재명/250909"

# base_path <- r"(C:\Users\adam\Desktop\차재명\새 폴더)"
to_r_path <- function(path) gsub("\\\\", "/", path)
project_path <- to_r_path(base_path)
data_path <- file.path(project_path, "data")
result_path <- file.path(project_path, "result2")
result_path2 <- file.path(project_path, "result3")

setwd(result_path)

################################################################################

# 그림 순서를 각 adverse event 항목에 대해 total, sub1, sub3, sub3, sub2+3순으로 정리해 주세요
# total, sub1, sub3, sub3, sub2+3

# list.files(result_path)

legend_names1 <- c("Conventional therapy","Advanced therapy","total",1)
legend_names2 <- c("Conventional therapy","Anti-TNF biologics","sub1",2)
legend_names3 <- c("Conventional therapy","Non-anti-TNF biologics","sub2",3)
legend_names4 <- c("Conventional therapy","Small molecule agent","sub3",5)
legend_names5 <- c("Conventional therapy","Non-anti-TNF AT","sub2+3",4)
m_table1<-as.data.table(rbind(legend_names1,legend_names2,legend_names3,legend_names4,legend_names5))
hr_table<-data.table()


for (j in 1:5) {

AEname<-paste0("O_",j)

pattern <- "^O.*\\.csv$"

AE1<-list.files(result_path,pattern = AEname)

text <-AE1[1]
pattern <- "O.*\\.csv"
match_pos <- regexpr(pattern, text)
matched_text <- regmatches(text, match_pos)

cleaned_text <- gsub("O_\\d+_", "", matched_text)
cleaned_text <- gsub(".csv", "", matched_text)

##################################################################################

for(i in 1:length(AE1)){

AE2<-list.files(result_path,pattern = AEname)[i]

m_table2<-m_table1[V4==i]

legend_names <- c(m_table2$V1,m_table2$V2)
cox_data<-fread(AE2)
# cox_data[, treatment := factor(treatment, levels = c("comparator","target"))]
cox_data[, treatment := factor(treatment, levels = c("target","comparator"))]

KM_fit <- survfit(Surv(survtime_day, outcomeCount) ~ treatment, data = cox_data, type = "kaplan-meier")


cox <- coxph(Surv(survtime_day, outcomeCount) ~ treatment, data = cox_data)
hr <- exp(coef(cox))
ci <- exp(confint(cox))
lrt <- survdiff(Surv(survtime_day, outcomeCount) ~ treatment, data = cox_data)
pv <- (1 - pchisq(lrt$chisq, length(lrt$n) - 1))

################################################################################
# 4. 생존분석 (KM plot 및 HR, CI, p값 계산)

KM_fit_plot <- ggsurvplot(
  KM_fit, 
  fun = "cumhaz",
  palette = c("#5048FF", "#ff7608"),
  surv.scale = "default",
  conf.int = FALSE, censor = FALSE,
  xlab = "Time (days)",
  ylab = "Cumulative hazard",
  font.x = c(15, "plain", "black"),
  font.y = c(15, "plain", "black"),
  font.tickslab = c(15, "plain", "black"),
  legend = "top", 
  legend.title = "",
  legend.labs = legend_names,
  font.legend = c(15, "plain", "black"),
  risk.table = TRUE,
  risk.table.title = "Number at risk by time", 
  risk.table.col = "black",
  risk.table.fontsize = 5,               # risk.table 폰트 크기 지정
  risk.table.y.text.col = TRUE,
  ggtheme = theme_classic(base_size = 15, base_family = "sans")+
    theme(
      axis.title.y = element_text(margin = margin(r = -130,l = -10))
      ),
  tables.theme = theme_classic(base_size = 15, base_family = "sans")+
    theme(
      axis.text.x = element_text(size = 15, face = "plain", color = "black"),
      plot.title = element_text(size = 15, face = "plain", color = "black"),
      # plot.margin = margin(l = -10)
    ),  # risk.table에도 테마 적용
  xlim = c(0, 3650),
  break.time.by = 365
)

print(KM_fit_plot)

# total, sub1, sub3, sub3, sub2+3

t1<-c(cleaned_text,m_table2$V4,m_table2$V3,round(pv, 3), round(hr, 3),round(ci[1], 3),round(ci[2], 3))

hr_table<-rbind(hr_table,t(t1))

tiff(paste0(result_path2,"/",cleaned_text,"_",m_table2$V4,"_",m_table2$V3,".tiff"), width=800, height=600, units="px")
print(KM_fit_plot)
dev.off()

  }

}

colnames(hr_table)<-c("outcome_name","num","group","Pv","HR","95% CI Lower","95% CI Upper")

hr_table[,num2:=num]
hr_table[num==5,num2:=4]
hr_table[num==4,num2:=5]

hr_table<-hr_table[order(outcome_name,num2)]

hr_table[,num:=NULL]

setnames(hr_table,"num2","order")

fwrite(hr_table,"hr_table.csv")




# if (grepl("windows", names(dev.cur()), ignore.case = TRUE)) {
#   # Windows 장치: sans가 어디에 매핑됐는지
#   windowsFonts()$sans   # 보통 "TT Arial"
# } else {
#   # ragg / Cairo / RStudioGD: systemfonts가 실제 폰트 선택
#   systemfonts::match_font("sans")  # 폰트 이름과 파일 경로가 나옵니다
# }


# KM_fit_plot$plot <- KM_fit_plot$plot + 
#   theme(text = element_text(family = "sans"),
#         axis.title.y.right = element_text(family = "sans"),
#         axis.text.y.right  = element_text(family = "sans"))
# 
# KM_fit_plot$table <- KM_fit_plot$table + 
#   theme(text = element_text(family = "sans"))
# 
# KM_fit_plot
# 
# names(dev.cur())
# systemfonts::match_font("sans")
# 
# KM_fit_plot$plot <- KM_fit_plot$plot +
#   coord_cartesian(clip = "off") 
  # theme(
  #   axis.title.y.right = element_text(
  #     size = 15, family = "Arial",
  #     hjust = 50   # 1보다 큰 값 → 더 붙여짐
  #   )
  # )

# target_size <- 15  # "Time (days)"와 같은 크기로 통일
# try(
#   tiff(
#     paste0(
#       gsub("/","",study_name), "_",
#       "t_", t_name, "_",
#       "c_", c_name, "_",
#       "o_", o_name, "_",
#       "s_", this_study, "_KM.tiff"
#     ),
#     width = 800, height = 600, units = "px"))
#   
# try(print(KM_fit_plot))


# try(grDevices::graphics.off(), silent = TRUE)
# dev.off()
# dev.list()   # 열려있는 기기 나열
# dev.cur()    # 현재 기기
# 
# 
# save_km_tiff <- function(km_obj, file, width=800, height=600, units="px") {
#   tiff(file, width=width, height=height, units=units)
#   on.exit(dev.off(), add = TRUE)  # 이 블록을 벗어날 때 반드시 닫음
#   print(km_obj)
# }






# names(dev.cur())
# 
# KM_fit_plot$plot$theme$text$family
# 
# windowsFonts()
# # $sans [1] "TT Arial"
# 
# 
# # windowsFonts(sans = windowsFont("Arial"))

